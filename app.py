# app.py
import os
import re
import base64
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ================== Page / Theme ==================
st.set_page_config(page_title="Market Nova", layout="wide")

# Auto-refresh every 5 minutes (300,000 ms)
st_autorefresh(interval=300_000, key="auto5min")

# ================== Utilities ==================
def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_csv(path: str) -> pd.DataFrame:
    try:
        if os.path.exists(path):
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()

def legend(title: str, lines: list[str]):
    with st.expander(f"Legend — {title}", expanded=False):
        st.markdown("\n".join([f"- {ln}" for ln in lines]))

def kpi_row(items):
    cols = st.columns(len(items))
    for col, (lbl, val) in zip(cols, items):
        col.metric(lbl, val)

# ================== Banner ==================
def _img_b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode("utf-8")

def show_market_nova_banner():
    img_path = Path("market_nova_brand.png")
    if not img_path.exists():
        return
    b64 = _img_b64(img_path)
    st.markdown(
        f"""
        <style>
        .nova-hero {{
          --h: min(20vh, 160px);
          width: 100%;
          height: var(--h);
          border-radius: 14px;
          background-image: url("data:image/png;base64,{b64}");
          background-size: cover;
          background-position: center;
          background-repeat: no-repeat;
          margin: 8px 0 6px 0;
        }}
        </style>
        <div class="nova-hero"></div>
        """,
        unsafe_allow_html=True,
    )

# ================== Dashboard ==================
def dashboard_tab():
    st.header("Dashboard")

    uni   = load_csv("data/universe_today.csv")
    news  = load_csv("data/news_scored.csv")
    pulse = load_csv("data/pulse_scores.csv")
    files = load_csv("data/sec_filings.csv")
    chat  = load_csv("data/chatter_summary.csv")

    tickers_scored = (pulse["ticker"].nunique() if {"ticker"} <= set(pulse.columns) else 0)
    avg_attn = (int(chat["Overall_Attention"].mean()) if not chat.empty and "Overall_Attention" in chat.columns else 0)

    kpi_row([
        ("Universe size", f"{len(uni) if not uni.empty else 0}"),
        ("Headlines scored", f"{len(news) if not news.empty else 0}"),
        ("SEC filings", f"{len(files) if not files.empty else 0}"),
        ("Tickers with scores", f"{tickers_scored}"),
        ("Avg Attention (0-100)", f"{avg_attn}"),
    ])

    st.subheader("Top 10 Setups (Attention Score)")
    if not pulse.empty and {"ticker","score"}.issubset(pulse.columns):
        cols = [c for c in ["ticker","news_sentiment","x_chatter_change","score"] if c in pulse.columns]
        top = pulse.sort_values("score", ascending=False).head(10)[cols].copy()
        top = top.rename(columns={
            "ticker": "Ticker",
            "news_sentiment": "News Buzz",
            "x_chatter_change": "Social Buzz",
            "score": "Attention Score",
        })
        st.dataframe(top, hide_index=True)
    else:
        st.info("No composite scores yet. Run `python run_once.py`.")

    st.caption(f"Last refresh: {now_text()}")

# ================== Discovery ==================
def discovery_tab():
    st.header("Discovery - Find Up-and-Coming Setups")

    legend("Discovery",
    [
        "**Ticker** - stock symbol",
        "**Volume Spike (x)** - today vs 20-day average",
        "**20-Day Breakout** - 1 if high > prior 20-day high",
        "**RSI Crossed 50** - 1 if RSI(14) crossed 50 today",
        "**Daily Change %** - today return vs yesterday",
        "**Gap Up 5%+** - 1 if open >= 5% above yesterday",
        "**News Sentiment** - average headline sentiment",
        "**Discovery Score** - combined signal",
        "**Last Close** - last close price",
        "**Prev Close** - prior close",
        "**Open** - today open",
        "**Trend** - sparkline of recent prices",
    ])

    path = "data/universe_today.csv"
    if not os.path.exists(path):
        st.error("Universe file not found. Run `python prep_discovery.py`.")
        return

    df = pd.read_csv(path)

    rename_map = {
        "ticker": "Ticker",
        "vol_spike": "Volume Spike (x)",
        "breakout20": "20-Day Breakout",
        "rsi_cross_50": "RSI Crossed 50",
        "pct_change": "Daily Change %",
        "gap_up_5": "Gap Up 5%+",
        "news_sentiment": "News Sentiment",
        "score": "Discovery Score",
        "last_close": "Last Close",
        "prev_close": "Prev Close",
        "open": "Open",
        "spark": "Trend",
    }
    df_display = df.rename(columns=rename_map).copy()

    # Sort by Discovery Score
    if "Discovery Score" in df_display.columns:
        df_display = df_display.sort_values("Discovery Score", ascending=False)

    st.data_editor(
        df_display,
        hide_index=True,
        disabled=True,
        use_container_width=True,
        column_config={
            "Trend": st.column_config.LineChartColumn("Trend", help="Recent closes"),
        },
    )

    st.caption(f"Last refresh: {now_text()}")

# ================== News Tab ==================
def news_tab():
    st.header("News Sentiment")
    path = "data/news_scored.csv"
    if os.path.exists(path):
        st.dataframe(pd.read_csv(path), hide_index=True)
    else:
        st.info("No news sentiment yet.")
    st.caption(f"Last refresh: {now_text()}")

# ================== Chatter ==================
def chatter_tab():
    st.header("Chatter")
    st.caption("Aggregated attention scores (0-100).")
    path = "data/chatter_summary.csv"
    if os.path.exists(path):
        st.dataframe(pd.read_csv(path).head(50), hide_index=True)
    else:
        st.info("No chatter yet.")
    st.caption(f"Last refresh: {now_text()}")

# ================== SEC ==================
def sec_tab():
    st.header("SEC Filings")
    path = "data/sec_filings.csv"
    if os.path.exists(path):
        st.dataframe(pd.read_csv(path).head(20), hide_index=True)
    else:
        st.info("No filings yet.")
    st.caption(f"Last refresh: {now_text()}")

# ================== Layout ==================
st.title("Market Nova")
show_market_nova_banner()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Dashboard", "🔍 Discovery", "📰 News Sentiment", "📈 Chatter", "📄 SEC Filings"]
)
with tab1: dashboard_tab()
with tab2: discovery_tab()
with tab3: news_tab()
with tab4: chatter_tab()
with tab5: sec_tab()