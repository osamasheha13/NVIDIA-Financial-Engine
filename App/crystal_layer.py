# ============================================================
# Project      : Financial Data Engineering — Layer 3 (Crystal)
# Description  : Streamlit dashboard for financial KPI visualization
#                and What-If scenario simulation.
#                Styled with NVIDIA brand colors (black + green).
# Dependencies : pip install streamlit pandas sqlalchemy plotly
# ============================================================
#
# NOTE ON THIS VERSION: switched from SQL Server to a local SQLite
# file (data/FinancialEngine.db) so the app can run on Streamlit
# Community Cloud with zero server setup — the .db file is part of
# the repo and ships with the deployment. All dashboard logic,
# styling, and charts below are unchanged from the original design.
# ============================================================

import os

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ============================================================
# PAGE CONFIG  (must be first Streamlit call)
# ============================================================

st.set_page_config(
    page_title="NVDA — Financial Intelligence Suite",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# NVIDIA BRAND THEME
# ============================================================

NVIDIA_GREEN  = "#76B900"
NVIDIA_BLACK  = "#ffffff"
NVIDIA_DARK   = "#f8f9fa"
NVIDIA_GRAY   = "#ffffff"
NVIDIA_LGRAY  = "#e0e0e0"
NVIDIA_TEXT   = "#1a1a1a"
NVIDIA_MUTED  = "#888888"
PLOTLY_THEME  = "plotly_white"

# ============================================================
# GLOBAL CSS
# ============================================================

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;600;700;800&family=Barlow+Condensed:wght@600;700;800&display=swap');

    /* ---- Base ---- */
    html, body, [class*="css"] {{
        font-family: 'Barlow', sans-serif;
        background-color: {NVIDIA_DARK};
        color: {NVIDIA_TEXT};
    }}
    .stApp {{ background-color: {NVIDIA_DARK}; }}

    /* ---- Hide default Streamlit chrome ---- */
    #MainMenu, footer {{ visibility: hidden; }}
    header {{ background-color: transparent !important; }}

    /* ---- Sidebar ---- */
    [data-testid="stSidebar"] {{
        background-color: {NVIDIA_BLACK};
        border-right: 1px solid {NVIDIA_GREEN}33;
    }}
    [data-testid="stSidebar"] .stSlider > div > div > div > div {{
        background-color: {NVIDIA_GREEN} !important;
    }}
    [data-testid="stSidebar"] label {{
        color: {NVIDIA_TEXT} !important;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }}

    /* ---- Metric cards ---- */
    [data-testid="stMetric"] {{
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid {NVIDIA_LGRAY};
        border-top: 3px solid {NVIDIA_GREEN};
        border-radius: 6px;
        padding: 20px 24px;
        transition: border-color 0.2s ease;
    }}
    [data-testid="stMetric"]:hover {{
        border-top-color: #8fd400;
    }}
    [data-testid="stMetricLabel"] {{
        color: {NVIDIA_MUTED} !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }}
    [data-testid="stMetricValue"] {{
        color: #1a1a1a !important;
        font-family: 'Barlow Condensed', sans-serif !important;
        font-size: 1.9rem !important;
        font-weight: 700 !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-size: 0.85rem !important;
        font-weight: 600 !important;
    }}

    /* ---- Section headers ---- */
    .section-header {{
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: {NVIDIA_GREEN};
        border-bottom: 1px solid {NVIDIA_GREEN}44;
        padding-bottom: 6px;
        margin: 28px 0 16px 0;
    }}

    /* ---- Hero banner ---- */
    .hero-banner {{
        background: linear-gradient(135deg, #f0f2f6 0%, #ffffff 100%);
        border: 1px solid #76B900;
        border-left: 4px solid {NVIDIA_GREEN};
        border-radius: 8px;
        padding: 28px 36px;
        margin-bottom: 32px;
        position: relative;
        overflow: hidden;
        color: #1a1a1a;
    }}
    .hero-banner::before {{
        content: '';
        position: absolute;
        top: -40px; right: -40px;
        width: 200px; height: 200px;
        background: radial-gradient({NVIDIA_GREEN}22, transparent 70%);
        border-radius: 50%;
    }}
    .hero-title {{
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 2.4rem;
        font-weight: 800;
        color: #1a1a1a;
        letter-spacing: 0.05em;
        margin: 0;
        line-height: 1.1;
    }}
    .hero-subtitle {{
        color: {NVIDIA_MUTED};
        font-size: 0.9rem;
        font-weight: 400;
        margin-top: 6px;
        letter-spacing: 0.05em;
    }}
    .hero-badge {{
        display: inline-block;
        background-color: {NVIDIA_GREEN}22;
        color: {NVIDIA_GREEN};
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        padding: 3px 10px;
        border-radius: 3px;
        border: 1px solid {NVIDIA_GREEN}55;
        margin-bottom: 10px;
    }}

    /* ---- Scenario result box ---- */
    .scenario-box {{
        background: #ffffff;
        border: 1px solid {NVIDIA_GREEN}55;
        border-radius: 8px;
        padding: 20px 24px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }}
    .scenario-box .label {{
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: {NVIDIA_MUTED};
        margin-bottom: 4px;
    }}
    .scenario-box .value {{
        font-family: 'Barlow Condensed', sans-serif;
        font-size: 2rem;
        font-weight: 800;
        color: {NVIDIA_GREEN};
    }}
    .scenario-box .delta {{
        font-size: 0.8rem;
        font-weight: 600;
        margin-top: 2px;
    }}
    .positive {{ color: {NVIDIA_GREEN}; }}
    .negative {{ color: #ff4c4c; }}

    /* ---- Tabs ---- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background-color: {NVIDIA_BLACK};
        border-radius: 6px;
        padding: 4px;
        border: 1px solid {NVIDIA_LGRAY};
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent;
        color: {NVIDIA_MUTED};
        font-weight: 600;
        font-size: 0.8rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border-radius: 4px;
        padding: 8px 20px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {NVIDIA_GREEN} !important;
        color: {NVIDIA_BLACK} !important;
    }}

    /* ---- Divider ---- */
    hr {{ border-color: {NVIDIA_LGRAY}; }}
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATABASE CONNECTION
# ============================================================

# Path to the SQLite file committed inside the repo's data/ folder.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "FinancialEngine.db")


@st.cache_resource
def get_engine():
    """
    Connect to the local SQLite database file shipped inside the repo.
    No server, no driver, no credentials — just a file on disk that
    Streamlit Cloud reads the same way your machine does.
    """
    return create_engine(f"sqlite:///{DB_PATH}")


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    """
    Load all rows from the Silver Layer Fact table.
    Cached for 5 minutes to avoid repeated DB hits on re-renders.
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT * FROM Fact_Internal_Metrics ORDER BY FiscalYear ASC"), conn)
        return df
    except SQLAlchemyError as e:
        st.error(f"Database connection failed: {e}")
        return pd.DataFrame()


# ============================================================
# PLOTLY CHART HELPERS
# ============================================================

CHART_LAYOUT = dict(
    template=PLOTLY_THEME,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Barlow, sans-serif", color='#1a1a1a', size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    hoverlabel=dict(bgcolor=NVIDIA_GRAY, font_size=12, font_family="Barlow"),
)

LEGEND_STYLE = dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11))
AXIS_STYLE = dict(gridcolor=NVIDIA_LGRAY, linecolor=NVIDIA_LGRAY, tickfont=dict(size=11))


def bar_line_chart(df, bar_col, line_col, bar_label, line_label, title, y_format=".2s", pct_format=False):
    """Combo bar + line chart with NVIDIA green palette."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["FiscalYear"], y=df[bar_col],
        name=bar_label,
        marker_color=NVIDIA_GREEN,
        marker_line_width=0,
        opacity=0.85,
    ))
    fig.add_trace(go.Scatter(
        x=df["FiscalYear"], y=df[line_col],
        name=line_label,
        mode="lines+markers",
        line=dict(color="#ffffff", width=2, dash="dot"),
        marker=dict(size=6, color="#ffffff"),
        yaxis="y2",
    ))
    fig.update_layout(**CHART_LAYOUT,
        legend=LEGEND_STYLE,
        title=dict(text=title, font=dict(size=14, color=NVIDIA_TEXT), x=0),
        yaxis2=dict(
            overlaying="y", side="right",
            tickformat=".0%" if pct_format else y_format,
            gridcolor="rgba(0,0,0,0)",
            tickfont=dict(size=11, color=NVIDIA_MUTED),
        ),
    )
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE, tickformat=y_format)
    return fig


def margin_area_chart(df, cols, labels, title):
    """Stacked area chart for margin trends."""
    colors = [NVIDIA_GREEN, "#4a8c00", "#2d5c00"]
    fig = go.Figure()
    for col, label, color in zip(cols, labels, colors):
        fig.add_trace(go.Scatter(
            x=df["FiscalYear"], y=df[col],
            name=label,
            fill="tozeroy",
            mode="lines",
            line=dict(color=color, width=2),
            fillcolor="rgba(118,185,0,0.2)" if color == NVIDIA_GREEN else ("rgba(74,140,0,0.2)" if color == "#4a8c00" else "rgba(45,92,0,0.2)"),
        ))
    fig.update_layout(**CHART_LAYOUT,
        legend=LEGEND_STYLE,
        title=dict(text=title, font=dict(size=14, color=NVIDIA_TEXT), x=0),
    )
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE, tickformat=".0%")
    return fig


def waterfall_chart(base_rev, sim_rev, base_ni, sim_ni):
    """Waterfall comparison: Baseline vs Scenario."""
    fig = go.Figure(go.Waterfall(
        name="Scenario Impact",
        orientation="v",
        measure=["absolute", "relative", "absolute", "relative", "total"],
        x=["Base Revenue", "Revenue Δ", "Base Net Income", "NI Δ", "Simulated NI"],
        y=[base_rev, sim_rev - base_rev, base_ni, sim_ni - base_ni, 0],
        connector=dict(line=dict(color=NVIDIA_LGRAY, width=1)),
        decreasing=dict(marker_color="#ff4c4c"),
        increasing=dict(marker_color=NVIDIA_GREEN),
        totals=dict(marker_color="#4a8c00"),
        textposition="outside",
        texttemplate="%{y:.2s}",
    ))
    fig.update_layout(**CHART_LAYOUT,
        legend=LEGEND_STYLE,
        title=dict(text="Scenario Waterfall Analysis", font=dict(size=14, color=NVIDIA_TEXT), x=0),
        showlegend=False,
    )
    return fig


# ============================================================
# MAIN APP
# ============================================================

def main():
    df = load_data()

    if 'sidebar_state' not in st.session_state:
        st.session_state.sidebar_state = 'expanded'

    if df.empty:
        st.error("No data loaded. Please run Layer 1 and Layer 2 pipelines first.")
        st.stop()

    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    # ----------------------------------------------------------
    # HERO BANNER
    # ----------------------------------------------------------
    st.markdown(f"""
    <div class="hero-banner">
        <div class="hero-badge">Crystal Layer · Financial Intelligence Suite</div>
        <div class="hero-title">NVIDIA Corporation</div>
        <div class="hero-subtitle">
            Ticker: NVDA &nbsp;·&nbsp; FY{int(latest['FiscalYear'])} &nbsp;·&nbsp;
            Sector: Technology &nbsp;·&nbsp; Industry: Semiconductors
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ----------------------------------------------------------
    # SIDEBAR — What-If Simulator
    # ----------------------------------------------------------
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center; padding: 16px 0 8px 0;">
            <div style="font-family:'Barlow Condensed',sans-serif; font-size:1.4rem;
                        font-weight:800; color:{NVIDIA_GREEN}; letter-spacing:0.1em;">
                WHAT-IF SIMULATOR
            </div>
            <div style="font-size:0.75rem; color:{NVIDIA_MUTED}; margin-top:2px;">
                Scenario Engine · FY{int(latest['FiscalYear'])}
            </div>
        </div>
        <hr style="border-color:{NVIDIA_GREEN}33; margin: 8px 0 20px 0;">
        """, unsafe_allow_html=True)

        rev_change  = st.slider("Revenue Change (%)",          -50,  50,  0, step=1)
        cost_change = st.slider("Variable Cost Change (%)",    -20,  20,  0, step=1)
        capex_mult  = st.slider("CAPEX Multiplier (%)",         50, 200, 100, step=5)

        st.markdown("<hr style='border-color:#333; margin: 20px 0 12px 0;'>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="font-size:0.7rem; color:{NVIDIA_MUTED}; line-height:1.6;">
            Adjustments are applied to the most recent fiscal year ({int(latest['FiscalYear'])}).
            Results are indicative estimates only.
        </div>
        """, unsafe_allow_html=True)

    # ----------------------------------------------------------
    # SCENARIO CALCULATIONS
    # ----------------------------------------------------------
    base_revenue   = latest["TotalRevenue"]
    base_ni        = latest["NetIncome"]
    base_fcf       = latest["FreeCashFlow"]

    sim_revenue    = base_revenue * (1 + rev_change / 100)
    sim_var_cost   = sim_revenue * (latest["Variable_Cost_Ratio"] * (1 + cost_change / 100))
    sim_fixed      = base_revenue * (1 - latest["Variable_Cost_Ratio"]) * (1 - latest["Operating_Margin_Pct"])
    sim_ni         = sim_revenue - sim_var_cost - sim_fixed
    sim_margin     = sim_ni / sim_revenue if sim_revenue != 0 else 0
    sim_capex      = latest["CapitalExpenditures"] * (capex_mult / 100)
    sim_fcf        = latest["OperatingCashFlow"] * (1 + rev_change / 100) - abs(sim_capex)

    ni_delta_pct   = (sim_ni - base_ni) / abs(base_ni) if base_ni != 0 else 0
    fcf_delta_pct  = (sim_fcf - base_fcf) / abs(base_fcf) if base_fcf != 0 else 0

    # ----------------------------------------------------------
    # TABS
    # ----------------------------------------------------------
    tab1, tab2, tab3 = st.tabs(["📈  Performance", "💡  What-If Scenario", "📋  Raw Data"])

    # ==================== TAB 1: PERFORMANCE ====================
    with tab1:

        st.markdown('<div class="section-header">Key Performance Indicators</div>', unsafe_allow_html=True)
        k1, k2, k3, k4, k5 = st.columns(5)

        k1.metric(
            "Total Revenue",
            f"${latest['TotalRevenue']/1e9:.1f}B",
            f"{latest.get('Revenue_Growth_YoY', 0)*100:.1f}% YoY",
        )
        k2.metric(
            "Gross Margin",
            f"{latest['Gross_Margin_Pct']*100:.1f}%",
            f"{(latest['Gross_Margin_Pct'] - prev['Gross_Margin_Pct'])*100:+.1f}pp",
        )
        k3.metric(
            "Operating Margin",
            f"{latest['Operating_Margin_Pct']*100:.1f}%",
            f"{(latest['Operating_Margin_Pct'] - prev['Operating_Margin_Pct'])*100:+.1f}pp",
        )
        k4.metric(
            "Free Cash Flow",
            f"${latest['FreeCashFlow']/1e9:.1f}B",
            f"{latest.get('FCF_Growth_YoY', 0)*100:.1f}% YoY",
        )
        k5.metric(
            "Return on Equity",
            f"{latest['ROE']*100:.1f}%",
            f"{(latest['ROE'] - prev['ROE'])*100:+.1f}pp",
        )

        st.markdown("")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="section-header">Revenue & Net Income</div>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df["FiscalYear"], y=df["TotalRevenue"],
                name="Revenue", marker_color=NVIDIA_GREEN, opacity=0.85, marker_line_width=0,
            ))
            fig.add_trace(go.Bar(
                x=df["FiscalYear"], y=df["NetIncome"],
                name="Net Income", marker_color="#4a8c00", opacity=0.85, marker_line_width=0,
            ))
            fig.update_layout(**CHART_LAYOUT, barmode="group", legend=LEGEND_STYLE)
            fig.update_xaxes(**AXIS_STYLE)
            fig.update_yaxes(**AXIS_STYLE, tickformat=".2s")
            st.plotly_chart(fig, width='stretch')

        with c2:
            st.markdown('<div class="section-header">Margin Trends</div>', unsafe_allow_html=True)
            fig = margin_area_chart(
                df,
                ["Gross_Margin_Pct", "Operating_Margin_Pct", "Net_Margin_Pct"],
                ["Gross Margin", "Operating Margin", "Net Margin"],
                "",
            )
            st.plotly_chart(fig, width='stretch')

        c3, c4 = st.columns(2)
        with c3:
            st.markdown('<div class="section-header">Free Cash Flow vs CAPEX</div>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df["FiscalYear"], y=df["FreeCashFlow"],
                name="Free Cash Flow", marker_color=NVIDIA_GREEN, opacity=0.85, marker_line_width=0,
            ))
            fig.add_trace(go.Bar(
                x=df["FiscalYear"], y=df["CapitalExpenditures"],
                name="CAPEX", marker_color="#ff4c4c", opacity=0.7, marker_line_width=0,
            ))
            fig.update_layout(**CHART_LAYOUT, barmode="group", legend=LEGEND_STYLE)
            fig.update_xaxes(**AXIS_STYLE)
            fig.update_yaxes(**AXIS_STYLE, tickformat=".2s")
            st.plotly_chart(fig, width='stretch')

        with c4:
            st.markdown('<div class="section-header">ROE vs ROA</div>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["FiscalYear"], y=df["ROE"],
                name="ROE", mode="lines+markers",
                line=dict(color=NVIDIA_GREEN, width=2),
                marker=dict(size=7, color=NVIDIA_GREEN),
            ))
            fig.add_trace(go.Scatter(
                x=df["FiscalYear"], y=df["ROA"],
                name="ROA", mode="lines+markers",
                line=dict(color="#ffffff", width=2, dash="dot"),
                marker=dict(size=7, color="#ffffff"),
            ))
            fig.update_layout(**CHART_LAYOUT, legend=LEGEND_STYLE)
            fig.update_xaxes(**AXIS_STYLE)
            fig.update_yaxes(**AXIS_STYLE, tickformat=".0%")
            st.plotly_chart(fig, width='stretch')

    # ==================== TAB 2: WHAT-IF ====================
    with tab2:

        st.markdown('<div class="section-header">Scenario Results — Most Recent Fiscal Year</div>', unsafe_allow_html=True)

        s1, s2, s3, s4 = st.columns(4)

        def delta_html(val):
            cls = "positive" if val >= 0 else "negative"
            sign = "▲" if val >= 0 else "▼"
            return f'<span class="{cls}">{sign} {abs(val)*100:.1f}%</span>'

        with s1:
            st.markdown(f"""
            <div class="scenario-box">
                <div class="label">Simulated Revenue</div>
                <div class="value">${sim_revenue/1e9:.2f}B</div>
                <div class="delta">{delta_html(rev_change/100)}</div>
            </div>""", unsafe_allow_html=True)

        with s2:
            st.markdown(f"""
            <div class="scenario-box">
                <div class="label">Simulated Net Income</div>
                <div class="value">${sim_ni/1e9:.2f}B</div>
                <div class="delta">{delta_html(ni_delta_pct)}</div>
            </div>""", unsafe_allow_html=True)

        with s3:
            st.markdown(f"""
            <div class="scenario-box">
                <div class="label">Simulated Net Margin</div>
                <div class="value">{sim_margin*100:.1f}%</div>
                <div class="delta">{delta_html(sim_margin - latest['Net_Margin_Pct'])}</div>
            </div>""", unsafe_allow_html=True)

        with s4:
            st.markdown(f"""
            <div class="scenario-box">
                <div class="label">Simulated FCF</div>
                <div class="value">${sim_fcf/1e9:.2f}B</div>
                <div class="delta">{delta_html(fcf_delta_pct)}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        w1, w2 = st.columns([3, 2])

        with w1:
            st.markdown('<div class="section-header">Waterfall Analysis</div>', unsafe_allow_html=True)
            fig = waterfall_chart(base_revenue, sim_revenue, base_ni, sim_ni)
            st.plotly_chart(fig, width='stretch')

        with w2:
            st.markdown('<div class="section-header">Baseline vs Scenario</div>', unsafe_allow_html=True)
            compare_df = pd.DataFrame({
                "Metric": ["Revenue", "Net Income", "FCF"],
                "Baseline": [base_revenue/1e9, base_ni/1e9, base_fcf/1e9],
                "Scenario": [sim_revenue/1e9, sim_ni/1e9, sim_fcf/1e9],
            })
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Baseline", x=compare_df["Metric"], y=compare_df["Baseline"],
                marker_color=NVIDIA_LGRAY, marker_line_width=0,
            ))
            fig.add_trace(go.Bar(
                name="Scenario", x=compare_df["Metric"], y=compare_df["Scenario"],
                marker_color=NVIDIA_GREEN, marker_line_width=0,
            ))
            fig.update_layout(**CHART_LAYOUT,
                barmode="group",
                legend={**LEGEND_STYLE, "orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
            )
            fig.update_xaxes(**AXIS_STYLE)
            fig.update_yaxes(**AXIS_STYLE, title="$ Billions")
            st.plotly_chart(fig, width='stretch')

        st.markdown('<div class="section-header">Operating Leverage Sensitivity</div>', unsafe_allow_html=True)
        rev_scenarios  = [-30, -20, -10, 0, 10, 20, 30, 50]
        ni_outcomes    = [
            (base_revenue * (1 + r/100) - base_revenue * (1 + r/100) * latest["Variable_Cost_Ratio"] - sim_fixed) / 1e9
            for r in rev_scenarios
        ]
        colors_bar = [NVIDIA_GREEN if v >= 0 else "#ff4c4c" for v in ni_outcomes]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=[f"{r:+d}%" for r in rev_scenarios],
            y=ni_outcomes,
            marker_color=colors_bar,
            marker_line_width=0,
            text=[f"${v:.1f}B" for v in ni_outcomes],
            textposition="outside",
            textfont=dict(size=11),
        ))
        fig.add_hline(y=base_ni/1e9, line_dash="dot", line_color=NVIDIA_MUTED, line_width=1,
                      annotation_text="Baseline NI", annotation_font_color=NVIDIA_MUTED)
        fig.update_layout(**CHART_LAYOUT, height=320, legend=LEGEND_STYLE)
        fig.update_xaxes(**AXIS_STYLE, title="Revenue Change Scenario")
        fig.update_yaxes(**AXIS_STYLE, title="Net Income ($B)")
        st.plotly_chart(fig, width='stretch')

    # ==================== TAB 3: RAW DATA ====================
    with tab3:
        st.markdown('<div class="section-header">Silver Layer — Full Dataset</div>', unsafe_allow_html=True)

        pct_cols = [c for c in df.columns if any(x in c for x in ["Pct", "Margin", "ROE", "ROA", "Ratio", "Growth", "Intensity", "Leverage", "Turnover"])]
        display_df = df.copy()
        for col in pct_cols:
            if col in display_df.columns:
                display_df[col] = (display_df[col] * 100).round(2).astype(str) + "%"

        dollar_cols = ["TotalRevenue", "CostOfRevenue", "GrossProfit", "OperatingIncome",
                       "NetIncome", "TotalAssets", "TotalLiabilities", "TotalStockholdersEquity",
                       "CashAndCashEquivalents", "Inventory", "OperatingCashFlow",
                       "CapitalExpenditures", "FreeCashFlow"]
        for col in dollar_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"${float(x)/1e9:.2f}B" if pd.notna(x) and x != "" else x)

        st.dataframe(
            display_df,
            width='stretch',
            hide_index=True,
        )

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇  Download Raw CSV",
            data=csv,
            file_name="nvda_silver_layer.csv",
            mime="text/csv",
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
