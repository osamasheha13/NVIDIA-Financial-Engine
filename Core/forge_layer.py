# ============================================================
# Project      : Financial Data Engineering — Layer 2 (Forge / Silver)
# Description  : Reads raw financial data from Layer 1 tables,
#                computes KPIs and analytical metrics, and writes
#                the results to the Fact_Internal_Metrics table.
# Dependencies : pip install pandas sqlalchemy
# ============================================================
#
# NOTE ON THIS VERSION: switched from SQL Server to a local SQLite
# file so the whole pipeline can run anywhere, including Streamlit
# Community Cloud, with zero server setup. All KPI logic below is
# unchanged from the original design.
# ============================================================

import os
import logging

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ============================================================
# LOGGING SETUP
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION  <- Edit here only
# ============================================================

TICKER: str = "NVDA"   # <- Change target company here

DB_PATH: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "FinancialEngine.db")

OUTPUT_TABLE: str = "Fact_Internal_Metrics"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_engine():
    """
    Build and return a SQLAlchemy engine for the local SQLite file.
    Same .db file used by Layer 1 — no separate setup needed.
    """
    engine = create_engine(f"sqlite:///{DB_PATH}")
    logger.info("Engine created -> %s", DB_PATH)
    return engine


# ============================================================
# DATA EXTRACTION
# ============================================================

EXTRACTION_QUERY = """
    SELECT
        i.Ticker,
        i.FiscalYear,

        -- Income Statement
        i.TotalRevenue,
        i.CostOfRevenue,
        i.GrossProfit,
        i.OperatingIncome,
        i.NetIncome,

        -- Balance Sheet
        b.TotalAssets,
        b.TotalLiabilities,
        b.TotalStockholdersEquity,
        b.Inventory,
        b.CashAndCashEquivalents,

        -- Cash Flow
        c.OperatingCashFlow,
        c.CapitalExpenditures,
        c.FreeCashFlow

    FROM      Raw_IncomeStatement  i
    JOIN      Raw_BalanceSheet     b
        ON    i.Ticker = b.Ticker AND i.FiscalYear = b.FiscalYear
    JOIN      Raw_CashFlow         c
        ON    i.Ticker = c.Ticker AND i.FiscalYear = c.FiscalYear
    WHERE     i.Ticker = :ticker
    ORDER BY  i.FiscalYear ASC;
"""


def extract_raw_data(engine, ticker: str) -> pd.DataFrame:
    """
    Pull joined raw financial data from the three Layer 1 tables
    for a single ticker, ordered by fiscal year ascending.

    Args:
        engine : SQLAlchemy engine
        ticker : Stock ticker symbol

    Returns:
        DataFrame with all raw financial fields needed for KPI computation
    """
    logger.info("Extracting raw data for %s ...", ticker)

    with engine.connect() as conn:
        df = pd.read_sql(text(EXTRACTION_QUERY), conn, params={"ticker": ticker})

    if df.empty:
        raise ValueError(
            f"No data found for ticker '{ticker}'. "
            "Ensure Layer 1 ingestion has been run first."
        )

    logger.info("  Extracted %d fiscal years.", len(df))
    return df


# ============================================================
# METRIC COMPUTATION
# ============================================================

def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all Silver Layer KPIs from the raw financial data.

    Metric groups:
        1. Profitability margins
        2. Asset efficiency & turnover
        3. Cash flow quality
        4. YoY growth rates
        5. What-If scenario drivers

    Args:
        df : Raw DataFrame extracted from Layer 1 (sorted by FiscalYear ASC)

    Returns:
        DataFrame enriched with all computed metrics
    """
    df = df.copy()

    # ----------------------------------------------------------
    # 1. PROFITABILITY MARGINS
    # ----------------------------------------------------------
    df["Gross_Margin_Pct"] = df["GrossProfit"] / df["TotalRevenue"]
    df["Operating_Margin_Pct"] = df["OperatingIncome"] / df["TotalRevenue"]
    df["Net_Margin_Pct"] = df["NetIncome"] / df["TotalRevenue"]

    # ----------------------------------------------------------
    # 2. ASSET EFFICIENCY & TURNOVER
    # ----------------------------------------------------------
    df["Asset_Turnover"] = df["TotalRevenue"] / df["TotalAssets"]
    df["Inventory_to_Revenue"] = df["Inventory"] / df["TotalRevenue"]
    df["ROE"] = df["NetIncome"] / df["TotalStockholdersEquity"]
    df["ROA"] = df["NetIncome"] / df["TotalAssets"]
    df["Debt_to_Equity"] = df["TotalLiabilities"] / df["TotalStockholdersEquity"]

    # ----------------------------------------------------------
    # 3. CASH FLOW QUALITY
    # ----------------------------------------------------------
    df["FCF_Margin"] = df["FreeCashFlow"] / df["TotalRevenue"]
    df["CF_Conversion"] = df["OperatingCashFlow"] / df["OperatingIncome"]
    df["Capex_Intensity"] = df["CapitalExpenditures"].abs() / df["TotalRevenue"]

    # ----------------------------------------------------------
    # 4. YoY GROWTH RATES
    # ----------------------------------------------------------
    df["Revenue_Growth_YoY"] = df["TotalRevenue"].pct_change()
    df["NetIncome_Growth_YoY"] = df["NetIncome"].pct_change()
    df["FCF_Growth_YoY"] = df["FreeCashFlow"].pct_change()

    # ----------------------------------------------------------
    # 5. WHAT-IF SCENARIO DRIVERS
    # ----------------------------------------------------------
    df["Variable_Cost_Ratio"] = df["CostOfRevenue"] / df["TotalRevenue"]
    df["Operating_Leverage"] = df["GrossProfit"] / df["OperatingIncome"]

    logger.info("  Computed %d KPI columns.", len(df.columns))
    return df


# ============================================================
# DATA LOADING
# ============================================================

def load_silver_layer(engine, df: pd.DataFrame) -> None:
    """
    Write the enriched DataFrame to the Silver Layer output table.
    Uses 'replace' strategy to ensure idempotent re-runs.

    Args:
        engine : SQLAlchemy engine
        df     : Enriched DataFrame with all computed metrics
    """
    if df.empty:
        logger.warning("Empty DataFrame — skipping write to %s.", OUTPUT_TABLE)
        return

    try:
        df.to_sql(OUTPUT_TABLE, engine, if_exists="replace", index=False)
        logger.info("  Written %d rows -> %s", len(df), OUTPUT_TABLE)
    except SQLAlchemyError as exc:
        logger.error("  Failed to write %s: %s", OUTPUT_TABLE, exc)
        raise


# ============================================================
# AUDIT & PREVIEW
# ============================================================

def run_audit(df: pd.DataFrame) -> None:
    """
    Print a preview of the key computed metrics to verify output quality.

    Args:
        df : Enriched Silver Layer DataFrame
    """
    preview_cols = [
        "FiscalYear",
        "Gross_Margin_Pct",
        "Operating_Margin_Pct",
        "Net_Margin_Pct",
        "ROE",
        "FCF_Margin",
        "Revenue_Growth_YoY",
    ]

    available = [c for c in preview_cols if c in df.columns]

    print(f"\n{'='*70}")
    print(f"SILVER LAYER PREVIEW — {df['Ticker'].iloc[0]}  ({len(df)} fiscal years)")
    print("=" * 70)
    print(df[available].to_string(index=False, float_format="{:.2%}".format))
    print("=" * 70)


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_silver_pipeline() -> None:
    """
    Execute the full Layer 2 (Silver) transformation pipeline:
        1. Connect to SQLite
        2. Extract joined raw data from Layer 1 tables
        3. Compute KPIs and analytical metrics
        4. Write results to Fact_Internal_Metrics
        5. Print audit preview
    """
    ticker = TICKER.upper().strip()

    logger.info("=" * 55)
    logger.info("Starting Layer 2 (Silver) pipeline for: %s", ticker)
    logger.info("=" * 55)

    engine = get_engine()
    df_raw = extract_raw_data(engine, ticker)
    df_enriched = compute_metrics(df_raw)
    load_silver_layer(engine, df_enriched)
    run_audit(df_enriched)

    logger.info("=" * 55)
    logger.info("Layer 2 complete for %s", ticker)
    logger.info("=" * 55)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_silver_pipeline()
