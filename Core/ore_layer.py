# ============================================================
# Project      : Financial Data Engineering — Layer 1
# Description  : Fetches financial statements from yfinance,
#                cleans them with pandas, and loads them into
#                Microsoft SQL Server (FinancialEngineDB).
# Dependencies : pip install yfinance pandas sqlalchemy pyodbc
# ============================================================

import urllib
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

# --- SQL Server connection settings ---
DB_CONFIG: dict = {
    "driver":             "{ODBC Driver 17 for SQL Server}",       # ODBC driver name
    "server":             "localhost\\SQLEXPRESS",   # e.g. localhost\\SQLEXPRESS
    "database":           "FinancialEngineDB",
    "trusted_connection": "yes",                # Windows Auth; set to 'no' for SQL Auth
    # "uid":             "your_username",       # Uncomment for SQL Auth
    # "pwd":             "your_password",       # Uncomment for SQL Auth
}

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
    "Capital Expenditure":  "CapitalExpenditures",   # ← كان "Capital Expenditures" (بدون s)
    "Free Cash Flow":       "FreeCashFlow",
    "Investing Cash Flow":  "InvestingCashFlow",
    "Financing Cash Flow":  "FinancingCashFlow",
}


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_engine():
    """
    Build and return a SQLAlchemy engine for SQL Server via pyodbc.
    Uses Windows Authentication by default (Trusted_Connection=yes).
    """
    odbc_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"Trusted_Connection={DB_CONFIG['trusted_connection']};"
    )
    # Uncomment below for SQL Server Authentication:
    # odbc_str += f"UID={DB_CONFIG['uid']};PWD={DB_CONFIG['pwd']};"

    params = urllib.parse.quote_plus(odbc_str)
    engine = create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}",
        fast_executemany=True,  # Significantly speeds up bulk inserts
    )
    logger.info("SQLAlchemy engine created → %s / %s", DB_CONFIG["server"], DB_CONFIG["database"])
    return engine


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
    logger.info("Fetching data for %s …", ticker)
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
        col_map : Mapping of yfinance column names → SQL column names
        ticker  : Stock ticker symbol

    Returns:
        Cleaned DataFrame ready for SQL insert
    """
    # Transpose: rows become fiscal periods, columns become line items
    df = df.T.copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "FiscalYear"
    df = df.reset_index()
    df["FiscalYear"] = df["FiscalYear"].dt.year
    df["Ticker"] = ticker

    # Keep only mapped columns that actually exist in the DataFrame
    available = {k: v for k, v in col_map.items() if k in df.columns}
    missing   = set(col_map.keys()) - set(available.keys())
    if missing:
        logger.warning("  [%s] Missing columns (will be skipped): %s", ticker, missing)

    selected = df[["Ticker", "FiscalYear"] + list(available.keys())].copy()
    selected.rename(columns=available, inplace=True)

    # Fill NaN and enforce float dtype for all financial columns
    numeric_cols = [c for c in selected.columns if c not in ("Ticker", "FiscalYear")]
    selected[numeric_cols] = selected[numeric_cols].fillna(0).astype(float)

    #Delete any year in which the base values ​​are zero.
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
    Uses a MERGE statement (SQL Server upsert) to avoid duplicates.

    Args:
        engine : SQLAlchemy engine
        ticker : Stock ticker symbol
        info   : Company metadata dict from yfinance
    """
    merge_sql = text("""
        MERGE dbo.CompanyInfo AS target
        USING (SELECT :ticker AS Ticker) AS source
        ON target.Ticker = source.Ticker
        WHEN MATCHED THEN
            UPDATE SET
                CompanyName = :name,
                Sector      = :sector,
                Industry    = :industry,
                Currency    = :currency
        WHEN NOT MATCHED THEN
            INSERT (Ticker, CompanyName, Sector, Industry, Currency)
            VALUES (:ticker, :name, :sector, :industry, :currency);
    """)

    with engine.begin() as conn:
        conn.execute(merge_sql, {
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
    Append a cleaned DataFrame to a SQL Server table.
    Skips the load if the DataFrame is empty.

    Args:
        engine : SQLAlchemy engine
        df     : Cleaned DataFrame
        table  : Target SQL table name (e.g., 'Raw_IncomeStatement')
        ticker : Ticker symbol (for logging only)
    """
    if df.empty:
        logger.warning("  [%s] Empty DataFrame — skipping load to %s.", ticker, table)
        return

    try:
        df.to_sql(table, engine, schema="dbo", if_exists="append", index=False)
        logger.info("  [%s] Loaded %d rows → dbo.%s", ticker, len(df), table)
    except SQLAlchemyError as exc:
        logger.error("  [%s] Failed to load dbo.%s: %s", ticker, table, exc)
        raise


# ============================================================
# AUDIT QUERIES
# ============================================================

def run_audit(engine) -> None:
    """
    Run post-ingestion data integrity checks and print results.
    Checks:
        1. Income statement row counts per ticker and year.
        2. Balance sheet equation: Total Assets ≈ Liabilities + Equity.
    """
    logger.info("Running post-ingestion audit …")

    audits = {
        "Income Statement — row counts by ticker/year": """
            SELECT Ticker, FiscalYear, COUNT(*) AS [RowCount]
            FROM   dbo.Raw_IncomeStatement
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
            FROM dbo.Raw_BalanceSheet
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
        1. Connect to SQL Server
        2. For each ticker: fetch → clean → upsert company info → load statements
        3. Run audit queries

    Args:
        tickers : List of stock ticker symbols to process
    """
    engine = get_engine()

    for ticker in tickers:
        ticker = ticker.upper().strip()
        logger.info("=" * 50)
        logger.info("Processing ticker: %s", ticker)
        logger.info("=" * 50)

        try:
            # Step 1: Fetch raw data from Yahoo Finance
            income_raw, balance_raw, cashflow_raw, info = fetch_financials(ticker)

            # Step 2: Clean and map to SQL schema
            income, balance, cashflow = clean_all(income_raw, balance_raw, cashflow_raw, ticker)

            # Step 3: Upsert company metadata
            upsert_company_info(engine, ticker, info)

            # Step 4: Load financial statements into SQL Server
            load_to_sql(engine, income,   "Raw_IncomeStatement", ticker)
            load_to_sql(engine, balance,  "Raw_BalanceSheet",    ticker)
            load_to_sql(engine, cashflow, "Raw_CashFlow",        ticker)

            logger.info("[%s] ✓ Pipeline completed successfully.", ticker)

        except Exception as exc:
            logger.error("[%s] ✗ Pipeline failed: %s", ticker, exc)
            continue  # Continue with remaining tickers even if one fails

    # Step 5: Post-ingestion audit
    run_audit(engine)
    logger.info("Layer 1 ingestion complete for all tickers.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_pipeline([TICKER])