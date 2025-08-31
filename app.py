import os
import re
from datetime import datetime
from pathlib import Path
import base64

import pandas as pd
import streamlit as st

# ================== Page Settings ==================
st.set_page_config(page_title="Market Nova", layout="wide")

# ================== Banner ==================
def _img_b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode("utf-8")

def show_market_nova_banner():
    img_path = Path("market_nova_brand.png")
    if not img_path.exists():
        st.warning("Banner not found: market_nova_brand.png")
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
        ("Avg Attention (0–100)", f"{avg_attn}"),
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
        "**ticker** - stock symbol",
        "**vol_spike** - today volume divided by 20-day average",
        "**breakout20** - 1 if today high > prior 20-day high",
        "**rsi_cross_50** - 1 if RSI(14) crossed above 50 today",
        "**pct_change** - today percent return vs yesterday close",
        "**gap_up_5** - 1 if open >= 5 percent above yesterday close",
        "**news_sentiment** - average headline sentiment",
        "**score** - discovery score",
        "**last_close** - last close price",
    ])

    path = "data/universe_today.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)

        # Beginner-friendly headers
        rename_map = {
            "ticker": "Ticker",
            "vol_spike": "Volume Spike (x)",
            "breakout20": "20-Day Breakout",
            "rsi_cross_50": "RSI Crossed 50",
            "pct_change": "Daily Change %",
            "gap_up_5": "Gap Up 5%+",
            "news_sentiment": "News Sentiment (-1..+1)",
            "score": "Discovery Score",
            "last_close": "Last Close",
        }
        df_display = df.rename(columns=rename_map)

        # Optional cosmetic - replace NaN with "-"
        df_display = df_display.fillna("-")

        # Keep a sensible column order if present
        ordered = [
            "Ticker",
            "Volume Spike (x)",
            "20-Day Breakout",
            "RSI Crossed 50",
            "Daily Change %",
            "Gap Up 5%+",
            "News Sentiment (-1..+1)",
            "Discovery Score",
            "Last Close",
        ]
        cols = [c for c in ordered if c in df_display.columns] + \
               [c for c in df_display.columns if c not in ordered]
        df_display = df_display[cols]

        st.dataframe(df_display, hide_index=True)
    else:
        st.error("Universe file not found. Run `python prep_discovery.py` to build it.")

    st.caption(f"Last refresh: {now_text()}")

# ================== News ==================
def news_tab():
    st.header("News Sentiment")
    legend("News Sentiment",
    ["Ticker – symbol","Title – headline text","Sentiment – −1 bearish to +1 bullish"])
    path = "data/news_scored.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        st.dataframe(df, hide_index=True)
    else:
        st.info("No news sentiment yet. Run `python run_once.py`.")
    st.caption(f"Last refresh: {now_text()}")

# ================== Chatter ==================
def chatter_tab():
    st.header("Chatter")
    st.caption("Aggregates attention from multiple sources.")
    path = "data/chatter_summary.csv"
    df = load_csv(path)
    if not df.empty:
        st.dataframe(df.head(50), hide_index=True)
    else:
        st.info("No chatter yet. Run `python run_once.py`.")
    st.caption(f"Last refresh: {now_text()}")

# ================== SEC Filings ==================
FORM_IN_TITLE = re.compile(r"\b(8\-K|10\-Q|10\-K|S\-1|S\-3|424B[0-9A-Z]*|SC\s*13D|SC\s*13G)\b", re.IGNORECASE)

def sec_tab():
    st.header("SEC Filings")
    fpath = "data/sec_filings.csv"
    if not os.path.exists(fpath):
        st.warning("No SEC filings saved yet.")
        return
    df = pd.read_csv(fpath)
    st.dataframe(df.head(20), hide_index=True)
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