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
    st.header("Discovery – Find Up-and-Coming Setups")

    legend("Discovery (Beginner Explanations)",
    [
        "**Ticker** – stock symbol (e.g., OPEN).",
        "**Volume Spike (x)** – today’s trading volume ÷ 20-day average volume.",
        "**20-Day Breakout** – Yes if today > 20-day high.",
        "**RSI Crossed 50** – RSI momentum turned bullish if crossed 50.",
        "**Daily Change %** – move from yesterday’s close.",
        "**Gap Up 5%+** – Yes if opened >5% above prior close.",
        "**News Sentiment** – average headline sentiment (−1 to +1).",
        "**Discovery Score** – combined signals into one ranking.",
        "**Last Close** – last official close price.",
    ])

    path = "data/universe_today.csv"
    if not os.path.exists(path):
        st.error("Universe file not found. Run `python seed_universe.py`.")
        st.caption(f"Last refresh: {now_text()}")
        return

    df = pd.read_csv(path)

    # Add debug
    st.caption("Discovery layout v2.1")
    st.write("Raw CSV columns:", list(df.columns))

    # Enrich with news sentiment
    if "news_sentiment" not in df.columns:
        ns_path = "data/news_scored.csv"
        if os.path.exists(ns_path):
            ns = pd.read_csv(ns_path)
            if {"ticker","sentiment"} <= set(ns.columns):
                ns_agg = ns.groupby("ticker", as_index=False)["sentiment"].mean().rename(columns={"sentiment":"news_sentiment"})
                df = df.merge(ns_agg, on="ticker", how="left")

    # Compute Daily % and Gap Up if missing
    if "pct_change" not in df.columns:
        if {"last_close","prev_close"} <= set(df.columns):
            df["pct_change"] = (df["last_close"] - df["prev_close"]) / df["prev_close"] * 100.0
        else:
            df["pct_change"] = pd.NA

    if "gap_up_5" not in df.columns:
        if {"open","prev_close"} <= set(df.columns):
            df["gap_up_5"] = ((df["open"] - df["prev_close"]) / df["prev_close"] >= 0.05).astype(int)
        else:
            df["gap_up_5"] = pd.NA

    def yes_no(col):
        if col not in df.columns: return pd.Series([pd.NA]*len(df))
        s = df[col]
        if s.dtype.kind in "biufc":
            return s.fillna(0).astype(int).map({1:"Yes",0:"No"})
        return s

    sort_col = "score" if "score" in df.columns else ("discovery_score" if "discovery_score" in df.columns else None)
    if sort_col: df = df.sort_values(sort_col, ascending=False)

    display = pd.DataFrame()
    display["Ticker"] = df.get("ticker")
    display["Volume Spike (x)"] = df.get("vol_spike")
    display["20-Day Breakout"] = yes_no("breakout20")
    display["RSI Crossed 50"] = yes_no("rsi_cross_50")
    display["Daily Change %"] = df.get("pct_change")
    display["Gap Up 5%+"] = yes_no("gap_up_5")
    display["News Sentiment (-1..+1)"] = df.get("news_sentiment")
    display["Discovery Score"] = df.get("score", df.get("discovery_score"))
    display["Last Close"] = df.get("last_close", df.get("close"))

    st.write("Prepared display columns:", list(display.columns))

    st.data_editor(
        display,
        hide_index=True,
        use_container_width=True
    )

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