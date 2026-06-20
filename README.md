# NVIDIA Financial Intelligence Platform — SQLite Edition

This is the deployable version of the 3-layer financial analysis pipeline,
adapted from SQL Server to SQLite so it can run on Streamlit Community Cloud
with zero server setup.

## What changed from the original

Only the database layer. All KPI logic, chart code, and dashboard styling
are unchanged.

- `Core/ore_layer.py` (Layer 1) — fetches from yfinance, writes to a local
  SQLite file at `data/FinancialEngine.db` instead of SQL Server.
- `Core/forge_layer.py` (Layer 2) — reads from that same file, computes KPIs,
  writes the Silver layer table back into it.
- `App/crystal_layer.py` (Layer 3) — Streamlit dashboard reads from the same
  file. No connection string, no driver, no credentials.

## How to run it locally

```bash
pip install -r requirements.txt

# Step 1: pull and store NVDA's financials
python Core/ore_layer.py

# Step 2: compute KPIs
python Core/forge_layer.py

# Step 3: launch the dashboard
streamlit run App/crystal_layer.py
```

After step 2, `data/FinancialEngine.db` contains everything the dashboard
needs. That file is what makes deployment possible — once it exists, no
internet connection or live data fetch is required to view the dashboard.

## How to deploy on Streamlit Community Cloud

1. Run steps 1 and 2 above on your machine once, so `data/FinancialEngine.db`
   is generated.
2. Commit that `.db` file to the repo (don't gitignore the `data/` folder).
3. Push everything to GitHub.
4. Go to [share.streamlit.io](https://share.streamlit.io), connect this repo,
   and set the main file path to `App/crystal_layer.py`.
5. Deploy. The app reads the committed `.db` file directly — no setup needed
   on Streamlit's side.

## Adding more companies

Change `TICKER` at the top of `Core/ore_layer.py` and `Core/forge_layer.py`,
then re-run both. Each ticker's rows are stored independently, so the
database can hold many companies side by side without conflicts.

## 🧠 The "Why" behind the Project
As an **accounting** professional who self-studied **data engineering**, I built this system to solve the "chaos of data." In the corporate world, data is often raw and unstructured (Ore). This project proves that through structured engineering, we can refine that data into actionable, crystalline intelligence.
