# app.py

import os
import re
import base64
from pathlib import Path
from datetime import datetime
from ast import literal_eval

import pandas as pd
import streamlit as st

# optional but nice if installed
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=300_000, key="auto5min")  # 5 minutes
except Exception:
    pass

# ================== Page / Theme ==================
st.set_page_config(page_title="Market Nova", layout="wide")

# ================== Utils ==================
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
    with st.expander(f"Legend - {title}", expanded=False):
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

    tickers_scored = (pulse["ticker"].nunique() if "ticker" in pulse.columns else 0)
    avg_attn = (int(chat["Overall_Attention"].mean()) if "Overall_Attention" in chat.columns else 0)

    kpi_row([
        ("Universe size", f"{len(uni) if not uni.empty else 0}"),
        ("Headlines scored", f"{len(news) if not news.empty else 0}"),
        ("SEC filings", f"{len(files) if not files.empty else 0}"),
        ("Tickers with scores", f"{tickers_scored}"),
        ("Avg Attention (0-100)", f"{avg_attn}"),
    ])

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
        "**prev_close** - prior close",
        "**open** - today open",
        "**spark** - recent price series for the sparkline",
    ])

    path = "data/universe_today.csv"
    if not os.path.exists(path):
        st.error("Universe file not found. Run `python3 prep_discovery.py` to build it.")
        st.caption(f"Last refresh: {now_text()}")
        return

    df = pd.read_csv(path)

    # Parse spark string -> list
    if "spark" in df.columns:
        def _parse_spark(v):
            if isinstance(v, list):
                return v
            if isinstance(v, str) and v.strip().startswith("["):
                try:
                    return literal_eval(v)
                except Exception:
                    return []
            return []
        df["spark"] = df["spark"].apply(_parse_spark)

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
        "prev_close": "Prev Close",
        "open": "Open",
        "spark": "Trend",
    }
    df_display = df.rename(columns=rename_map).copy()

    # Numeric formatting (keep raw list for Trend)
    for c in ["Volume Spike (x)", "Daily Change %", "Last Close", "Prev Close", "Open", "Discovery Score"]:
        if c in df_display.columns:
            df_display[c] = pd.to_numeric(df_display[c], errors="coerce").round(2)

    # Column order
    ordered = [
        "Ticker", "Trend", "Volume Spike (x)", "20-Day Breakout", "RSI Crossed 50",
        "Daily Change %", "Gap Up 5%+", "News Sentiment (-1..+1)", "Discovery Score",
        "Last Close", "Prev Close", "Open",
    ]
    cols = [c for c in ordered if c in df_display.columns] + \
           [c for c in df_display.columns if c not in ordered]
    df_display = df_display[cols]

    # Sort by Discovery Score
    if "Discovery Score" in df_display.columns:
        df_display = df_display.sort_values("Discovery Score", ascending=False)

    st.data_editor(
        df_display,
        hide_index=True,
        disabled=True,
        use_container_width=True,
        column_config={
            "Trend": st.column_config.LineChartColumn(
                "Trend", width="small", help="Recent closing prices"
            ),
            "Volume Spike (x)": st.column_config.NumberColumn(format="%.2f", width="small"),
            "Daily Change %": st.column_config.NumberColumn(format="%.2f", width="small"),
            "Last Close": st.column_config.NumberColumn(format="%.2f", width="small"),
            "Prev Close": st.column_config.NumberColumn(format="%.2f", width="small"),
            "Open": st.column_config.NumberColumn(format="%.2f", width="small"),
            "20-Day Breakout": st.column_config.NumberColumn(width="small"),
            "RSI Crossed 50": st.column_config.NumberColumn(width="small"),
            "Gap Up 5%+": st.column_config.NumberColumn(width="small"),
            "News Sentiment (-1..+1)": st.column_config.NumberColumn(format="%.2f", width="small"),
            "Discovery Score": st.column_config.NumberColumn(format="%.2f", width="small"),
        },
    )

    st.caption(f"Last refresh: {now_text()}")

# ================== News ==================
def news_tab():
    st.header("News Sentiment")
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
    st.caption("Aggregates attention from multiple sources. Scores are normalized to 0-100.")
    summary_path = "data/chatter_summary.csv"
    long_path = "data/chatter.csv"

    summ = load_csv(summary_path)
    long = load_csv(long_path)

    if not summ.empty:
        show = summ.sort_values("Overall_Attention", ascending=False) if "Overall_Attention" in summ.columns else summ
        st.subheader("Summary (0-100)")
        st.dataframe(show.head(50), hide_index=True)
    else:
        st.info("No chatter summary yet. Run `python run_once.py`.")

    if not long.empty:
        with st.expander("Per-source leaders", expanded=False):
            for src in ["trends", "reddit_rss", "reddit_api", "stocktwits", "gdelt", "wiki"]:
                sub = long[long["source"] == src].copy()
                if sub.empty:
                    continue
                if "score_100" in sub.columns:
                    sub = sub.sort_values("score_100", ascending=False)
                st.markdown(f"**{src}**")
                cols = [c for c in ["ticker","score_100","value","change_pct"] if c in sub.columns]
                st.dataframe(sub[cols].head(20), hide_index=True)

    st.caption(f"Last refresh: {now_text()}")

# ================== SEC ==================
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
    last_time_txt = "-" if pd.isna(last_time) else last_time.tz_convert("America/New_York").strftime("%Y-%m-%d %H:%M ET")
    total_rows = len(df)

    st.info(f"Latest filing time: **{last_time_txt}** • Total rows: **{total_rows}**")

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

with tab1:
    dashboard_tab()
with tab2:
    discovery_tab()
with tab3:
    news_tab()
with tab4:
    chatter_tab()
with tab5:
    sec_tab()