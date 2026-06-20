# ============================================================
# Project      : Financial Data Engineering — Layer 1 (Ore)
# Description  : Fetches financial statements from yfinance,
#                cleans them with pandas, and loads them into
#                a local SQLite database (FinancialEngine.db).
# Dependencies : pip install yfinance pandas sqlalchemy
# ============================================================
#
# NOTE ON THIS VERSION:
# This file was originally written against Microsoft SQL Server
# (pyodbc + Trusted_Connection). That works great locally but
# can't run on Streamlit Community Cloud, which has no SQL Server
# to connect to. SQLite solves this: it's a single file-based
# database with zero setup, so the same .db file that's created
# here can be committed to the repo and read directly by the
# Streamlit app, anywhere.
#
# Everything else — the fetching, cleaning, and schema logic —
# is unchanged from the original design.
# ============================================================

import os
import logging

import pandas as pd
import yfinance as yf
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
# CONFIGURATION
# ============================================================

# --- Target ticker ---
TICKER: str = "NVDA"

# --- SQLite database path ---
# This file lives inside the repo (data/) so it can be committed
# to GitHub and read by Streamlit Cloud without any server setup.
DB_PATH: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "FinancialEngine.db")

# --- Column mappings: yfinance label → SQL column name ---

INCOME_COLS: dict[str, str] = {
    "Total Revenue":       "TotalRevenue",
    "Cost Of Revenue":     "CostOfRevenue",
    "Gross Profit":        "GrossProfit",
    "Operating Income":    "OperatingIncome",
    "Net Income":          "NetIncome",
    "EBITDA":              "EBITDA",
}

BALANCE_COLS: dict[str, str] = {
    "Total Assets":                            "TotalAssets",
    "Total Liabilities Net Minority Interest": "TotalLiabilities",
    "Stockholders Equity":                     "TotalStockholdersEquity",
    "Cash And Cash Equivalents":               "CashAndCashEquivalents",
    "Inventory":                               "Inventory",
    "Current Assets":                          "TotalCurrentAssets",
    "Current Liabilities":                     "TotalCurrentLiabilities",
    "Total Debt":                              "TotalDebt",
}

CASHFLOW_COLS: dict[str, str] = {
    "Operating Cash Flow":  "OperatingCashFlow",
    "Capital Expenditure":  "CapitalExpenditures",
    "Free Cash Flow":       "FreeCashFlow",
    "Investing Cash Flow":  "InvestingCashFlow",
    "Financing Cash Flow":  "FinancingCashFlow",
}


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_engine():
    """
    Build and return a SQLAlchemy engine for a local SQLite file.

    SQLite needs no server, no driver install, and no credentials —
    the "database" is just the .db file on disk. This makes the
    project portable: the same engine call works identically on a
    laptop or on Streamlit Community Cloud.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    engine = create_engine(f"sqlite:///{DB_PATH}")
    logger.info("SQLAlchemy engine created -> %s", DB_PATH)
    return engine


def init_schema(engine) -> None:
    """
    Create the CompanyInfo table if it doesn't already exist.
    The Raw_* statement tables are created automatically by
    pandas.to_sql() on first load, so only CompanyInfo (which
    uses an upsert) needs an explicit CREATE TABLE.
    """
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS CompanyInfo (
                Ticker      TEXT PRIMARY KEY,
                CompanyName TEXT,
                Sector      TEXT,
                Industry    TEXT,
                Currency    TEXT
            );
        """))


# ============================================================
# DATA FETCHING
# ============================================================

def fetch_financials(ticker: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Download annual financial statements and company metadata
    from Yahoo Finance for a given ticker symbol.

    Returns:
        income_raw    : Raw annual income statement (columns = fiscal dates)
        balance_raw   : Raw annual balance sheet
        cashflow_raw  : Raw annual cash flow statement
        info          : Company metadata dictionary
    """
    logger.info("Fetching data for %s ...", ticker)
    company = yf.Ticker(ticker)

    income_raw   = company.financials      # Income Statement
    balance_raw  = company.balance_sheet   # Balance Sheet
    cashflow_raw = company.cashflow        # Cash Flow Statement
    info         = company.info            # Company metadata

    if income_raw.empty:
        raise ValueError(f"No financial data returned for ticker: {ticker}")

    return income_raw, balance_raw, cashflow_raw, info


# ============================================================
# DATA CLEANING
# ============================================================

def _clean_statement(df: pd.DataFrame, col_map: dict[str, str], ticker: str) -> pd.DataFrame:
    """
    Generic cleaner for any financial statement DataFrame.

    Steps:
        1. Transpose so each row = one fiscal year.
        2. Extract the integer year from the datetime index.
        3. Add the Ticker column.
        4. Select and rename only the columns defined in col_map.
        5. Fill NaN with 0 (missing line items default to zero).
        6. Cast numeric columns to float.

    Args:
        df      : Raw DataFrame from yfinance (columns = fiscal dates, rows = line items)
        col_map : Mapping of yfinance column names -> SQL column names
        ticker  : Stock ticker symbol

    Returns:
        Cleaned DataFrame ready for SQL insert
    """
    df = df.T.copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "FiscalYear"
    df = df.reset_index()
    df["FiscalYear"] = df["FiscalYear"].dt.year
    df["Ticker"] = ticker

    available = {k: v for k, v in col_map.items() if k in df.columns}
    missing   = set(col_map.keys()) - set(available.keys())
    if missing:
        logger.warning("  [%s] Missing columns (will be skipped): %s", ticker, missing)

    selected = df[["Ticker", "FiscalYear"] + list(available.keys())].copy()
    selected.rename(columns=available, inplace=True)

    numeric_cols = [c for c in selected.columns if c not in ("Ticker", "FiscalYear")]
    selected[numeric_cols] = selected[numeric_cols].fillna(0).astype(float)

    if "TotalRevenue" in selected.columns:
        selected = selected[selected["TotalRevenue"] > 0]
    elif "TotalAssets" in selected.columns:
        selected = selected[selected["TotalAssets"] > 0]

    return selected


def clean_all(
    income_raw: pd.DataFrame,
    balance_raw: pd.DataFrame,
    cashflow_raw: pd.DataFrame,
    ticker: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Clean all three financial statements for a single ticker.

    Returns:
        income, balance, cashflow — cleaned DataFrames
    """
    income   = _clean_statement(income_raw,   INCOME_COLS,   ticker)
    balance  = _clean_statement(balance_raw,  BALANCE_COLS,  ticker)
    cashflow = _clean_statement(cashflow_raw, CASHFLOW_COLS, ticker)
    return income, balance, cashflow


# ============================================================
# COMPANY INFO UPSERT
# ============================================================

def upsert_company_info(engine, ticker: str, info: dict) -> None:
    """
    Insert or update company metadata in the CompanyInfo table.

    SQLite doesn't support T-SQL's MERGE statement, so this uses
    SQLite's native "INSERT ... ON CONFLICT DO UPDATE" upsert syntax
    instead. Functionally identical outcome to the original MERGE.

    Args:
        engine : SQLAlchemy engine
        ticker : Stock ticker symbol
        info   : Company metadata dict from yfinance
    """
    upsert_sql = text("""
        INSERT INTO CompanyInfo (Ticker, CompanyName, Sector, Industry, Currency)
        VALUES (:ticker, :name, :sector, :industry, :currency)
        ON CONFLICT(Ticker) DO UPDATE SET
            CompanyName = excluded.CompanyName,
            Sector      = excluded.Sector,
            Industry    = excluded.Industry,
            Currency    = excluded.Currency;
    """)

    with engine.begin() as conn:
        conn.execute(upsert_sql, {
            "ticker":   ticker[0] if isinstance(ticker, list) else ticker,
            "name":     info.get("longName",         "N/A"),
            "sector":   info.get("sector",            "N/A"),
            "industry": info.get("industry",          "N/A"),
            "currency": info.get("financialCurrency", "USD"),
        })

    logger.info("  [%s] CompanyInfo upserted.", ticker)


# ============================================================
# SQL LOADER
# ============================================================

def load_to_sql(engine, df: pd.DataFrame, table: str, ticker: str) -> None:
    """
    Append a cleaned DataFrame to a SQLite table.

    Because this script can be re-run for the same ticker (e.g. to
    refresh data), duplicate rows are removed first: any existing
    rows for this ticker are deleted before the fresh data is
    appended, keeping the table idempotent across re-runs.

    Args:
        engine : SQLAlchemy engine
        df     : Cleaned DataFrame
        table  : Target SQL table name (e.g., 'Raw_IncomeStatement')
        ticker : Ticker symbol (for logging and dedup)
    """
    if df.empty:
        logger.warning("  [%s] Empty DataFrame — skipping load to %s.", ticker, table)
        return

    try:
        with engine.begin() as conn:
            exists = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
            ), {"t": table}).fetchone()
            if exists:
                conn.execute(text(f"DELETE FROM {table} WHERE Ticker = :ticker"), {"ticker": ticker})

        df.to_sql(table, engine, if_exists="append", index=False)
        logger.info("  [%s] Loaded %d rows -> %s", ticker, len(df), table)
    except SQLAlchemyError as exc:
        logger.error("  [%s] Failed to load %s: %s", ticker, table, exc)
        raise


# ============================================================
# AUDIT QUERIES
# ============================================================

def run_audit(engine) -> None:
    """
    Run post-ingestion data integrity checks and print results.
    Checks:
        1. Income statement row counts per ticker and year.
        2. Balance sheet equation: Total Assets ~ Liabilities + Equity.
    """
    logger.info("Running post-ingestion audit ...")

    audits = {
        "Income Statement — row counts by ticker/year": """
            SELECT Ticker, FiscalYear, COUNT(*) AS RowCount
            FROM   Raw_IncomeStatement
            GROUP  BY Ticker, FiscalYear
            ORDER  BY Ticker, FiscalYear DESC;
        """,
        "Balance Sheet — Assets vs (Liabilities + Equity)": """
            SELECT
                Ticker,
                FiscalYear,
                TotalAssets,
                (TotalLiabilities + TotalStockholdersEquity) AS Sum_L_E,
                ABS(TotalAssets - (TotalLiabilities + TotalStockholdersEquity)) AS Diff
            FROM Raw_BalanceSheet
            ORDER BY Ticker, FiscalYear DESC;
        """,
    }

    with engine.connect() as conn:
        for label, query in audits.items():
            print(f"\n{'='*60}")
            print(f"AUDIT: {label}")
            print('='*60)
            result = pd.read_sql(text(query), conn)
            print(result.to_string(index=False))


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(tickers: list[str]) -> None:
    """
    Execute the full Layer 1 ingestion pipeline for all tickers:
        1. Connect to SQLite (creates the .db file if missing)
        2. For each ticker: fetch -> clean -> upsert company info -> load statements
        3. Run audit queries

    Args:
        tickers : List of stock ticker symbols to process
    """
    engine = get_engine()
    init_schema(engine)

    for ticker in tickers:
        ticker = ticker.upper().strip()
        logger.info("=" * 50)
        logger.info("Processing ticker: %s", ticker)
        logger.info("=" * 50)

        try:
            income_raw, balance_raw, cashflow_raw, info = fetch_financials(ticker)
            income, balance, cashflow = clean_all(income_raw, balance_raw, cashflow_raw, ticker)

            upsert_company_info(engine, ticker, info)

            load_to_sql(engine, income,   "Raw_IncomeStatement", ticker)
            load_to_sql(engine, balance,  "Raw_BalanceSheet",    ticker)
            load_to_sql(engine, cashflow, "Raw_CashFlow",        ticker)

            logger.info("[%s] Pipeline completed successfully.", ticker)

        except Exception as exc:
            logger.error("[%s] Pipeline failed: %s", ticker, exc)
            continue

    run_audit(engine)
    logger.info("Layer 1 ingestion complete for all tickers.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_pipeline([TICKER])
