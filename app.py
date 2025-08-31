import os
import re
from datetime import datetime, timedelta
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
    """
    Edge-to-edge, responsive hero banner.
    Uses market_nova_brand.png placed in the project root.
    """
    img_path = Path("market_nova_brand.png")
    if not img_path.exists():
        st.warning("Banner not found: market_nova_brand.png")
        return

    b64 = _img_b64(img_path)

    st.markdown(
        f"""
        <style>
        .nova-hero {{
          --h: min(20vh, 160px);           /* hero height */
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
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60 * 1000, key="auto_refresh")
except Exception:
    pass

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

        st.caption(
            "**Legend**\n"
            "- **Ticker**: stock symbol\n"
            "- **News Buzz**: unusual news activity vs baseline\n"
            "- **Social Buzz**: unusual online/social activity\n"
            "- **Attention Score**: combined News Buzz + Social Buzz"
        )
    else:
        st.info("No composite scores yet. Run `python run_once.py`.")

    st.caption(f"Last refresh: {now_text()}")

# ================== Discovery ==================
def discovery_tab():
    st.header("Discovery – Find Up-and-Coming Setups")

    # -------- Legend with beginner explanations --------
    legend("Discovery (Beginner Explanations)",
    [
        "**Ticker** – the stock symbol (e.g., OPEN).",
        "**Volume Spike (x)** – today’s trading volume divided by the stock’s 20-day average volume. "
        "Values above 1.0 mean more activity than usual (e.g., 2.0 = double normal).",
        "**20-Day Breakout** – 'Yes' if today’s price pushed above the highest price of the last 20 trading days. "
        "Breakouts can indicate strong buying interest.",
        "**RSI Crossed 50** – RSI (Relative Strength Index) moving above 50 can signal momentum shifting bullish. "
        "Below 50 often means momentum is weak; above 50 means improving.",
        "**Daily Change %** – percentage move from yesterday’s close to today’s last price.",
        "**Gap Up 5%+** – 'Yes' if today’s opening price was at least 5% above the prior close (a bullish sign of demand).",
        "**News Sentiment** – average headline sentiment scored from −1 (bearish) to +1 (bullish) for the day.",
        "**Discovery Score** – combined score that surfaces interesting setups using multiple signals.",
        "**Last Close** – last official closing price.",
    ])

    # -------- Load core universe --------
    path = "data/universe_today.csv"
    if not os.path.exists(path):
        st.error("Universe file not found. Run `python seed_universe.py`.")
        st.caption(f"Last refresh: {now_text()}")
        return

    df = pd.read_csv(path)

    # -------- Try to enrich with News Sentiment if missing --------
    if "news_sentiment" not in df.columns:
        ns_path = "data/news_scored.csv"
        if os.path.exists(ns_path):
            ns = pd.read_csv(ns_path)
            if {"ticker","sentiment"} <= set(ns.columns):
                ns_agg = ns.groupby("ticker", as_index=False)["sentiment"].mean().rename(columns={"sentiment":"news_sentiment"})
                df = df.merge(ns_agg, on="ticker", how="left")

    # -------- Create friendly display columns (compute where possible or leave blank) --------
    # Try to compute Daily Change % if not present
    if "pct_change" not in df.columns:
        # Try common column names to estimate percentage change
        if {"last_close","prev_close"} <= set(df.columns):
            with pd.option_context('mode.chained_assignment', None):
                df["pct_change"] = (df["last_close"] - df["prev_close"]) / df["prev_close"] * 100.0
        elif {"close","prev_close"} <= set(df.columns):
            df["pct_change"] = (df["close"] - df["prev_close"]) / df["prev_close"] * 100.0
        elif {"price","prev_close"} <= set(df.columns):
            df["pct_change"] = (df["price"] - df["prev_close"]) / df["prev_close"] * 100.0
        else:
            df["pct_change"] = pd.NA  # leave blank if we can't compute

    # Try to compute Gap Up 5%+ if not present
    if "gap_up_5" not in df.columns:
        if {"open","prev_close"} <= set(df.columns):
            df["gap_up_5"] = ((df["open"] - df["prev_close"]) / df["prev_close"] >= 0.05).astype(int)
        else:
            df["gap_up_5"] = pd.NA

    # Normalize binary indicators to Yes/No for display later
    def yes_no(col):
        if col not in df.columns: 
            return pd.Series([pd.NA]*len(df))
        series = df[col]
        if series.dtype.kind in "biufc":
            return series.fillna(0).astype(int).map({1:"Yes", 0:"No"})
        return series

    # -------- Decide sort column --------
    sort_col = "score" if "score" in df.columns else ("discovery_score" if "discovery_score" in df.columns else None)
    if sort_col:
        df = df.sort_values(sort_col, ascending=False)

    # -------- Build a display frame with beginner titles --------
    display = pd.DataFrame()
    display["Ticker"] = df.get("ticker")

    # Volume spike (x vs 20-day avg)
    display["Volume Spike (x)"] = df.get("vol_spike")

    # 20-day breakout and RSI cross (Yes/No)
    display["20-Day Breakout"] = yes_no("breakout20")
    display["RSI Crossed 50"] = yes_no("rsi_cross_50")

    # Daily change and gap up
    display["Daily Change %"] = df.get("pct_change")
    display["Gap Up 5%+"] = yes_no("gap_up_5")

    # News sentiment
    display["News Sentiment (-1..+1)"] = df.get("news_sentiment")

    # Discovery score
    if "score" in df.columns:
        display["Discovery Score"] = df["score"]
    elif "discovery_score" in df.columns:
        display["Discovery Score"] = df["discovery_score"]
    else:
        display["Discovery Score"] = pd.NA

    # Last close
    display["Last Close"] = df.get("last_close", df.get("close"))

    # -------- Render editor with sizing --------
    st.data_editor(
            # -------- Render editor with sizing and explicit order --------
    col_order = [
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

    st.data_editor(
        display,
        hide_index=True,
        use_container_width=True,
        column_order=col_order,
        column_config={
            "Ticker": st.column_config.TextColumn("Ticker", width="small"),
            "Volume Spike (x)": st.column_config.NumberColumn("Volume Spike (x)", help="Today’s volume ÷ 20-day average", width="small", step=0.1, format="%.2f"),
            "20-Day Breakout": st.column_config.TextColumn("20-Day Breakout", width="small"),
            "RSI Crossed 50": st.column_config.TextColumn("RSI Crossed 50", width="small"),
            "Daily Change %": st.column_config.NumberColumn("Daily Change %", help="Percent move from yesterday’s close", width="small", step=0.1, format="%.2f"),
            "Gap Up 5%+": st.column_config.TextColumn("Gap Up 5%+", width="small"),
            "News Sentiment (-1..+1)": st.column_config.NumberColumn("News Sentiment (-1..+1)", width="small", step=0.01, format="%.2f"),
            "Discovery Score": st.column_config.NumberColumn("Discovery Score", width="small", step=0.001, format="%.4f"),
            "Last Close": st.column_config.NumberColumn("Last Close", width="small", step=0.01, format="%.2f"),
        }
    )

    st.caption(f"Last refresh: {now_text()}")

# ================== News Sentiment ==================
def news_tab():
    st.header("News Sentiment")

    legend("News Sentiment",
    [
        "**ticker** – symbol",
        "**title** – headline text",
        "**sentiment** – −1 bearish to +1 bullish",
    ])

    path = "data/news_scored.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        if "link" in df.columns:
            df["link"] = df["link"].astype(str).str.slice(0, 80)
        st.dataframe(df, hide_index=True)
    else:
        st.info("No news sentiment data yet. Run `python run_once.py`.")

    st.caption(f"Last refresh: {now_text()}")

# ================== Chatter ==================
def chatter_tab():
    st.header("Chatter")

    st.caption("Aggregates attention from multiple sources. Scores are normalized to 0–100.")

    legend("Chatter",
    [
        "**ticker** – symbol",
        "**Overall_Attention** – avg (0–100) across sources",
        "May include: **trends**, **reddit**, **stocktwits**, **wiki**, etc.",
    ])

    summary_path = "data/chatter_summary.csv"
    long_path = "data/chatter.csv"

    summ = load_csv(summary_path)
    long = load_csv(long_path)

    if not summ.empty:
        show = summ.sort_values("Overall_Attention", ascending=False) if "Overall_Attention" in summ.columns else summ
        st.subheader("Summary (0–100)")
        st.dataframe(show.head(50), hide_index=True)
    else:
        st.info("No chatter summary yet. Run `python run_once.py`.")

    if not long.empty:
        with st.expander("Per-source leaders", expanded=False):
            for src in ["trends", "reddit_rss", "reddit_api", "stocktwits", "gdelt", "wiki"]:
                sub = long[long["source"] == src].copy()
                if sub.empty: continue
                if "score_100" in sub.columns:
                    sub = sub.sort_values("score_100", ascending=False)
                st.markdown(f"**{src}**")
                cols = [c for c in ["ticker","score_100","value","change_pct"] if c in sub.columns]
                st.dataframe(sub[cols].head(20), hide_index=True)

    st.caption(f"Last refresh: {now_text()}")

# ================== SEC Filings ==================
FORM_IN_TITLE = re.compile(r"\b(8\-K|10\-Q|10\-K|S\-1|S\-3|424B[0-9A-Z]*|SC\s*13D|SC\s*13G)\b", re.IGNORECASE)
TAG_CLEAN = re.compile(r"<[^>]*>")

def clean_company(val: str) -> str:
    if not isinstance(val, str):
        return ""
    return TAG_CLEAN.sub("", val).strip()

def backfill_form_from_title(df: pd.DataFrame) -> pd.DataFrame:
    if "title" not in df.columns:
        return df
    if "form" not in df.columns:
        df["form"] = None
    mask = df["form"].isna() | (df["form"].astype(str).str.strip() == "")
    if mask.any():
        found = df.loc[mask, "title"].astype(str).str.extract(FORM_IN_TITLE)[0]
        df.loc[mask, "form"] = found.fillna(df.loc[mask, "form"])
    df["form"] = df["form"].astype(str).str.upper().str.replace(r"\s+", "", regex=True)
    df["form"] = df["form"].str.replace("SC13D", "SC 13D").str.replace("SC13G", "SC 13G")
    return df

def sec_flag(form: str) -> str:
    if not isinstance(form, str):
        return "📝"
    f = form.upper().strip()
    if f.startswith("8-K") or f.startswith("S-1") or f.startswith("424B") or f in {"SC 13D","SC 13G"}:
        return "🔥"
    if f in {"10-Q","10-K"}:
        return "📘"
    return "📝"

def sec_tab():
    st.header("SEC Filings")

    fpath = "data/sec_filings.csv"
    if not os.path.exists(fpath):
        st.warning("No SEC filings saved yet.")
        return

    df = pd.read_csv(fpath)
    if df.empty:
        st.info("SEC filings file is empty.")
        return

    if "filed" in df.columns:
        df["filed"] = pd.to_datetime(df["filed"], errors="coerce", utc=True)
    if "company" in df.columns:
        df["company"] = df["company"].apply(clean_company)

    df = backfill_form_from_title(df)
    if "filed" in df.columns:
        df["filed_et"] = df["filed"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d %H:%M")

    last_time = df["filed"].max() if "filed" in df.columns else pd.NaT
    last_time_txt = "—" if pd.isna(last_time) else last_time.tz_convert("America/New_York").strftime("%Y-%m-%d %H:%M ET")
    total_rows = len(df)

    st.info(
        f"Latest filing time: **{last_time_txt}** • Total rows: **{total_rows}**"
    )

    df["signal"] = df.get("form", "").apply(sec_flag)
    latest = df.sort_values("filed", ascending=False) if "filed" in df.columns else df.copy()

    prefer = ["signal","ticker","form","filed_et","company","title","link"]
    show_cols = [c for c in prefer if c in latest.columns]

    st.subheader("Latest 20 Filings")
    st.caption("Legend: 🔥 hot (8-K/S-1/424B/SC 13D/G), 📘 financials (10-Q/10-K), 📝 other")
    st.dataframe(latest[show_cols].head(20), hide_index=True)

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