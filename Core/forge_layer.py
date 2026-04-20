# ============================================================
# Project      : Financial Data Engineering — Layer 2 (Silver)
# Description  : Reads raw financial data from Layer 1 tables,
#                computes KPIs and analytical metrics, and writes
#                the results to the Fact_Internal_Metrics table.
# Dependencies : pip install pandas sqlalchemy pyodbc
# ============================================================

import logging
import urllib

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

DB_CONFIG: dict = {
    "driver":             "{ODBC Driver 17 for SQL Server}",
    "server":             "localhost\\SQLEXPRESS",
    "database":           "FinancialEngineDB",
    "trusted_connection": "yes",
}

OUTPUT_TABLE: str = "Fact_Internal_Metrics"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_engine():
    """
    Build and return a SQLAlchemy engine for SQL Server via pyodbc.
    Uses Windows Authentication (Trusted_Connection=yes).
    """
    odbc_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"Trusted_Connection={DB_CONFIG['trusted_connection']};"
    )
    params = urllib.parse.quote_plus(odbc_str)
    engine = create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}",
        fast_executemany=True,
    )
    logger.info("Engine created -> %s / %s", DB_CONFIG["server"], DB_CONFIG["database"])
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

    FROM      dbo.Raw_IncomeStatement  i
    JOIN      dbo.Raw_BalanceSheet     b
        ON    i.Ticker = b.Ticker AND i.FiscalYear = b.FiscalYear
    JOIN      dbo.Raw_CashFlow         c
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

    # Gross Margin: how much revenue remains after direct costs
    df["Gross_Margin_Pct"] = df["GrossProfit"] / df["TotalRevenue"]

    # Operating Margin: profitability from core operations
    df["Operating_Margin_Pct"] = df["OperatingIncome"] / df["TotalRevenue"]

    # Net Profit Margin: bottom-line profitability
    df["Net_Margin_Pct"] = df["NetIncome"] / df["TotalRevenue"]

    # ----------------------------------------------------------
    # 2. ASSET EFFICIENCY & TURNOVER
    # ----------------------------------------------------------

    # Asset Turnover: revenue generated per dollar of assets
    df["Asset_Turnover"] = df["TotalRevenue"] / df["TotalAssets"]

    # Inventory to Revenue: measures inventory build-up relative to sales
    df["Inventory_to_Revenue"] = df["Inventory"] / df["TotalRevenue"]

    # Return on Equity (ROE): net income relative to shareholders equity
    df["ROE"] = df["NetIncome"] / df["TotalStockholdersEquity"]

    # Return on Assets (ROA): how efficiently assets generate profit
    df["ROA"] = df["NetIncome"] / df["TotalAssets"]

    # Debt to Equity Ratio: financial leverage indicator
    df["Debt_to_Equity"] = df["TotalLiabilities"] / df["TotalStockholdersEquity"]

    # ----------------------------------------------------------
    # 3. CASH FLOW QUALITY
    # ----------------------------------------------------------

    # FCF Margin: free cash flow as a percentage of revenue
    df["FCF_Margin"] = df["FreeCashFlow"] / df["TotalRevenue"]

    # Cash Flow Conversion: how much operating income converts to operating cash
    df["CF_Conversion"] = df["OperatingCashFlow"] / df["OperatingIncome"]

    # CAPEX Intensity: capital expenditure relative to revenue
    df["Capex_Intensity"] = df["CapitalExpenditures"].abs() / df["TotalRevenue"]

    # ----------------------------------------------------------
    # 4. YoY GROWTH RATES
    # ----------------------------------------------------------

    # Revenue growth year-over-year
    df["Revenue_Growth_YoY"] = df["TotalRevenue"].pct_change()

    # Net income growth year-over-year
    df["NetIncome_Growth_YoY"] = df["NetIncome"].pct_change()

    # Free cash flow growth year-over-year
    df["FCF_Growth_YoY"] = df["FreeCashFlow"].pct_change()

    # ----------------------------------------------------------
    # 5. WHAT-IF SCENARIO DRIVERS
    # ----------------------------------------------------------

    # Variable Cost Ratio: proportion of revenue consumed by variable costs (COGS)
    df["Variable_Cost_Ratio"] = df["CostOfRevenue"] / df["TotalRevenue"]

    # Operating Leverage: sensitivity of operating income to revenue changes
    # Higher ratio = higher fixed cost base = more sensitive to revenue swings
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
        df.to_sql(OUTPUT_TABLE, engine, schema="dbo", if_exists="replace", index=False)
        logger.info("  Written %d rows -> dbo.%s", len(df), OUTPUT_TABLE)
    except SQLAlchemyError as exc:
        logger.error("  Failed to write dbo.%s: %s", OUTPUT_TABLE, exc)
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
        1. Connect to SQL Server
        2. Extract joined raw data from Layer 1 tables
        3. Compute KPIs and analytical metrics
        4. Write results to dbo.Fact_Internal_Metrics
        5. Print audit preview
    """
    ticker = TICKER.upper().strip()

    logger.info("=" * 55)
    logger.info("Starting Layer 2 (Silver) pipeline for: %s", ticker)
    logger.info("=" * 55)

    # Step 1: Connect
    engine = get_engine()

    # Step 2: Extract
    df_raw = extract_raw_data(engine, ticker)

    # Step 3: Compute metrics
    df_enriched = compute_metrics(df_raw)

    # Step 4: Load to Silver Layer
    load_silver_layer(engine, df_enriched)

    # Step 5: Audit preview
    run_audit(df_enriched)

    logger.info("=" * 55)
    logger.info("Layer 2 complete for %s", ticker)
    logger.info("=" * 55)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_silver_pipeline()