-- ============================================================
-- Project      : Financial Engine Database
-- Description  : Core schema for storing financial statements
--                (Income Statement, Balance Sheet, Cash Flow)
--                for publicly traded companies.
-- Author       : Financial Engineering Team
-- Created      : 2025
-- Version      : 1.0
-- ============================================================

-- ============================================================
-- STEP 1: DATABASE CREATION
-- ============================================================

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'FinancialEngineDB')
BEGIN
    CREATE DATABASE FinancialEngineDB;
END
GO

USE FinancialEngineDB;
GO


-- ============================================================
-- STEP 2: COMPANY METADATA TABLE
-- Stores static reference data for each publicly traded company.
-- Acts as the parent table for all financial statement tables.
-- ============================================================

IF OBJECT_ID('dbo.CompanyInfo', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CompanyInfo (
        Ticker          VARCHAR(10)     NOT NULL,   -- Stock ticker symbol (e.g., 'AAPL', 'MSFT')
        CompanyName     NVARCHAR(255)   NOT NULL,   -- Full legal company name
        Sector          NVARCHAR(100)       NULL,   -- GICS sector (e.g., 'Technology', 'Healthcare')
        Industry        NVARCHAR(100)       NULL,   -- GICS industry sub-classification
        Currency        VARCHAR(10)         NULL,   -- Reporting currency (e.g., 'USD', 'EUR')

        -- Primary Key
        CONSTRAINT PK_CompanyInfo PRIMARY KEY (Ticker)
    );
END
GO


-- ============================================================
-- STEP 3: RAW INCOME STATEMENT TABLE
-- Stores annual income statement data per company.
-- Captures revenue, profitability, and EBITDA figures.
-- ============================================================

IF OBJECT_ID('dbo.Raw_IncomeStatement', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Raw_IncomeStatement (
        ID                  INT             NOT NULL IDENTITY(1,1),  -- Surrogate primary key (auto-increment)
        Ticker              VARCHAR(10)     NOT NULL,                -- Foreign key → CompanyInfo
        FiscalYear          INT             NOT NULL,                -- Fiscal year (e.g., 2023)
        TotalRevenue        FLOAT               NULL,                -- Top-line revenue / net sales
        CostOfRevenue       FLOAT               NULL,                -- Direct cost of goods sold (COGS)
        GrossProfit         FLOAT               NULL,                -- TotalRevenue - CostOfRevenue
        OperatingIncome     FLOAT               NULL,                -- Earnings before interest & tax (EBIT)
        NetIncome           FLOAT               NULL,                -- Bottom-line profit after all expenses & taxes
        EBITDA              FLOAT               NULL,                -- Earnings before interest, taxes, depreciation & amortization

        -- Primary Key
        CONSTRAINT PK_Raw_IncomeStatement PRIMARY KEY (ID),

        -- Foreign Key → CompanyInfo
        CONSTRAINT FK_IncomeStatement_Company
            FOREIGN KEY (Ticker) REFERENCES dbo.CompanyInfo(Ticker)
            ON DELETE CASCADE
            ON UPDATE CASCADE,

        -- Prevent duplicate fiscal year records per company
        CONSTRAINT UQ_IncomeStatement_Ticker_Year UNIQUE (Ticker, FiscalYear)
    );
END
GO


-- ============================================================
-- STEP 4: RAW BALANCE SHEET TABLE
-- Stores annual balance sheet snapshots per company.
-- Covers assets, liabilities, equity, and liquidity positions.
-- ============================================================

IF OBJECT_ID('dbo.Raw_BalanceSheet', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Raw_BalanceSheet (
        ID                          INT             NOT NULL IDENTITY(1,1),  -- Surrogate primary key
        Ticker                      VARCHAR(10)     NOT NULL,                -- Foreign key → CompanyInfo
        FiscalYear                  INT             NOT NULL,                -- Fiscal year end
        TotalAssets                 FLOAT               NULL,                -- Sum of all assets
        TotalLiabilities            FLOAT               NULL,                -- Sum of all liabilities
        TotalStockholdersEquity     FLOAT               NULL,                -- Book value (Assets - Liabilities)
        CashAndCashEquivalents      FLOAT               NULL,                -- Most liquid assets (cash + short-term investments)
        Inventory                   FLOAT               NULL,                -- Raw materials & finished goods on hand
        TotalCurrentAssets          FLOAT               NULL,                -- Assets convertible to cash within 12 months
        TotalCurrentLiabilities     FLOAT               NULL,                -- Obligations due within 12 months
        TotalDebt                   FLOAT               NULL,                -- Short-term + long-term debt obligations

        -- Primary Key
        CONSTRAINT PK_Raw_BalanceSheet PRIMARY KEY (ID),

        -- Foreign Key → CompanyInfo
        CONSTRAINT FK_BalanceSheet_Company
            FOREIGN KEY (Ticker) REFERENCES dbo.CompanyInfo(Ticker)
            ON DELETE CASCADE
            ON UPDATE CASCADE,

        -- Prevent duplicate fiscal year records per company
        CONSTRAINT UQ_BalanceSheet_Ticker_Year UNIQUE (Ticker, FiscalYear)
    );
END
GO


-- ============================================================
-- STEP 5: RAW CASH FLOW TABLE
-- Stores annual cash flow statement data per company.
-- Covers operating, investing, financing activities, and free cash flow.
-- ============================================================

IF OBJECT_ID('dbo.Raw_CashFlow', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Raw_CashFlow (
        ID                      INT             NOT NULL IDENTITY(1,1),  -- Surrogate primary key
        Ticker                  VARCHAR(10)     NOT NULL,                -- Foreign key → CompanyInfo
        FiscalYear              INT             NOT NULL,                -- Fiscal year
        OperatingCashFlow       FLOAT               NULL,                -- Cash generated from core business operations
        CapitalExpenditures     FLOAT               NULL,                -- CAPEX: spending on PP&E and long-term assets (typically negative)
        FreeCashFlow            FLOAT               NULL,                -- OperatingCashFlow - |CapitalExpenditures|
        InvestingCashFlow       FLOAT               NULL,                -- Cash used in investing activities (acquisitions, securities)
        FinancingCashFlow       FLOAT               NULL,                -- Cash from debt/equity issuance, dividends, buybacks

        -- Primary Key
        CONSTRAINT PK_Raw_CashFlow PRIMARY KEY (ID),

        -- Foreign Key → CompanyInfo
        CONSTRAINT FK_CashFlow_Company
            FOREIGN KEY (Ticker) REFERENCES dbo.CompanyInfo(Ticker)
            ON DELETE CASCADE
            ON UPDATE CASCADE,

        -- Prevent duplicate fiscal year records per company
        CONSTRAINT UQ_CashFlow_Ticker_Year UNIQUE (Ticker, FiscalYear)
    );
END
GO


-- ============================================================
-- INDEXES: Improve query performance on common filter patterns
-- ============================================================

-- Index for filtering income statements by ticker and fiscal year
CREATE NONCLUSTERED INDEX IX_IncomeStatement_Ticker_Year
    ON dbo.Raw_IncomeStatement (Ticker, FiscalYear);
GO

-- Index for filtering balance sheets by ticker and fiscal year
CREATE NONCLUSTERED INDEX IX_BalanceSheet_Ticker_Year
    ON dbo.Raw_BalanceSheet (Ticker, FiscalYear);
GO

-- Index for filtering cash flows by ticker and fiscal year
CREATE NONCLUSTERED INDEX IX_CashFlow_Ticker_Year
    ON dbo.Raw_CashFlow (Ticker, FiscalYear);
GO


-- ============================================================
-- END OF SCHEMA SETUP
-- ============================================================