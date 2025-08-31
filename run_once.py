# run_once.py — builds news/sentiment + chatter + SEC filings (with Atom-feed fallback)

import os
import re
import time
import pandas as pd

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:
    import tomli as tomllib

# Optional project modules (graceful fallbacks)
try:
    from src.ingest.news import fetch_headlines_for_ticker
except Exception:
    fetch_headlines_for_ticker = None

try:
    from src.nlp.sentiment import SentimentScorer
except Exception:
    SentimentScorer = None

try:
    from src.analysis.merge_signals import merge_and_score
except Exception:
    merge_and_score = None

# Original SEC puller (may fail/return nothing)
try:
    from src.ingest.sec import main as sec_pull
except Exception:
    sec_pull = None

# Our fallback uses feedparser (no API key, works with ticker)
try:
    import feedparser
except Exception:
    feedparser = None

# ------------------------------- helpers -------------------------------

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load_cfg(path="config.toml"):
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}

def load_universe_or_fallback():
    uni_path = os.path.join(DATA_DIR, "universe_today.csv")
    if os.path.exists(uni_path):
        try:
            u = pd.read_csv(uni_path)
            if "ticker" in u:
                lst = (
                    u["ticker"].dropna().astype(str).str.upper().unique().tolist()
                )
                if lst:
                    return lst
        except Exception:
            pass
    cfg = load_cfg()
    tickers = [str(t).upper() for t in cfg.get("tickers", [])]
    return tickers if tickers else ["OPEN", "AAPL", "MSFT"]

# ----------------------- news + sentiment (optional) -------------------

def build_news_and_sentiment(tickers, per=20):
    rows = []
    if fetch_headlines_for_ticker is None:
        print("News module not available; skipping news.")
        return pd.DataFrame()
    for t in tickers:
        try:
            items = fetch_headlines_for_ticker(t, per)
            rows.extend(items)
        except Exception as e:
            rows.append({"ticker": t, "title": f"[news error: {e}]", "link": "", "published": ""})
    news_df = pd.DataFrame(rows)
    if news_df.empty:
        return news_df

    if SentimentScorer is None:
        print("Sentiment module not available; writing raw headlines only.")
        news_df["sentiment"] = 0.0
        return news_df

    scorer = SentimentScorer()
    scores = scorer.score_texts(news_df["title"].fillna("").tolist())
    news_df["sentiment"] = [s.get("score", 0.0) for s in scores]
    return news_df

# ----------------------- attention (your 6 sources) --------------------

from src.alt.attention import aggregate_attention

def build_attention(tickers, cfg, ttl=3600, force_refresh=False):
    att = aggregate_attention(tickers, cfg=cfg, ttl=ttl, force_refresh=force_refresh)
    if att is None:
        att = pd.DataFrame()
    if not att.empty:
        wide = att.pivot_table(values="score_100", index="ticker", columns="source", aggfunc="mean").fillna(1)
        wide["Overall_Attention"] = wide.mean(axis=1).round().astype(int)
    else:
        wide = pd.DataFrame()
    return att, wide

# ---------------------------- SEC section ------------------------------

SEC_ATOM_TMPL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&owner=exclude&count=40&output=atom"

_FORM_RE = re.compile(r"Form\s+([A-Za-z0-9\-]+)", re.IGNORECASE)

def _parse_form_from_title(title: str) -> str:
    if not isinstance(title, str):
        return ""
    m = _FORM_RE.search(title)
    return m.group(1).upper() if m else ""

def fetch_sec_atom_for_ticker(ticker: str, user_agent: str, delay: float = 0.3, max_items: int = 20):
    """
    Fetch recent filings via SEC Atom feed using the ticker (no CIK needed).
    Returns list[dict] with keys: filed, ticker, form, company, title, link
    """
    out = []
    if feedparser is None:
        return out

    url = SEC_ATOM_TMPL.format(ticker=ticker)
    # feedparser lets us pass a UA via request_headers
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": user_agent})
    except Exception:
        return out

    if getattr(feed, "bozo", 0) != 0:
        # malformed feed; skip
        return out

    entries = getattr(feed, "entries", []) or []
    for e in entries[:max_items]:
        title = getattr(e, "title", "") or ""
        link = ""
        # Try to find a link href
        if hasattr(e, "links") and e.links:
            for ln in e.links:
                if isinstance(ln, dict) and ln.get("href"):
                    link = ln["href"]
                    break
        # Fallback: e.link attr
        if not link and hasattr(e, "link"):
            link = e.link

        company = getattr(e, "companyName", "") or getattr(e, "summary", "") or ""
        filed_raw = getattr(e, "updated", "") or getattr(e, "published", "")
        form = _parse_form_from_title(title)

        out.append(
            {
                "filed": filed_raw,
                "ticker": ticker,
                "form": form,
                "company": company,
                "title": title,
                "link": link,
            }
        )

    # polite gap between requests
    time.sleep(delay)
    return out

def build_sec(cfg, tickers):
    """
    Try the project's SEC puller first; if it returns nothing, fall back to Atom feeds.
    Writes data/sec_filings.csv when there is any data.
    """
    sec_cfg = cfg.get("sec", {})
    if not sec_cfg.get("enabled", False):
        print("SEC disabled in config.toml; skipping SEC.")
        return pd.DataFrame()

    ua = sec_cfg.get("user_agent") or "MarketPulsePro (marketpulsepro.app@gmail.com)"

    # 1) Try project's ingress
    df = pd.DataFrame()
    if sec_pull is not None:
        try:
            res = sec_pull()
            if isinstance(res, pd.DataFrame):
                df = res.copy()
            elif isinstance(res, list):
                df = pd.DataFrame(res)
        except Exception as e:
            print("SEC pull (project) error:", e)

    # 2) Fallback to Atom feeds if needed
    if df.empty:
        print("SEC: using Atom feed fallback...")
        rows = []
        for t in tickers:
            try:
                rows.extend(fetch_sec_atom_for_ticker(t, ua, delay=0.35, max_items=20))
            except Exception as e:
                rows.append({"ticker": t, "title": f"[sec atom error: {e}]", "link": "", "filed": "", "form": "", "company": ""})
        df = pd.DataFrame(rows)

    # If still empty, stop gracefully
    if df.empty:
        print("SEC: no filings found.")
        return df

    # Normalize columns
    rename_map = {
        "company_name": "company", "companyName": "company",
        "date": "filed", "filing_date": "filed",
        "formType": "form", "form_type": "form",
        "url": "link", "href": "link"
    }
    for a, b in rename_map.items():
        if a in df.columns and b not in df.columns:
            df = df.rename(columns={a: b})

    # Parse/standardize date
    if "filed" in df.columns:
        df["filed"] = pd.to_datetime(df["filed"], errors="coerce", utc=True)

    # Order columns
    cols = [c for c in ["filed", "ticker", "form", "company", "title", "link"] if c in df.columns]
    if cols:
        df = df[cols + [c for c in df.columns if c not in cols]]

    out = os.path.join(DATA_DIR, "sec_filings.csv")
    df.to_csv(out, index=False)
    print(f"Saved {len(df)} SEC filings -> {out}")
    return df

# ------------------------------- main ----------------------------------

def main():
    cfg = load_cfg()
    tickers = load_universe_or_fallback()
    print(f"Universe size: {len(tickers)}")

    # 1) NEWS + SENTIMENT
    per = cfg.get("news", {}).get("per_ticker", 20)
    news_df = build_news_and_sentiment(tickers, per=per)
    if not news_df.empty:
        news_df.to_csv(os.path.join(DATA_DIR, "news_scored.csv"), index=False)
        print(f"Saved {len(news_df)} headlines -> data/news_scored.csv")

    if merge_and_score is not None and not news_df.empty:
        try:
            pulse = merge_and_score(news_df, None)
            pulse.to_csv(os.path.join(DATA_DIR, "pulse_scores.csv"), index=False)
            print("Saved data/pulse_scores.csv")
        except Exception as e:
            print("merge_and_score error (continuing):", e)

    # 2) ATTENTION (6 sources)
    att_long, att_wide = build_attention(tickers, cfg, ttl=3600, force_refresh=False)
    att_long.to_csv(os.path.join(DATA_DIR, "chatter.csv"), index=False)
    att_wide.to_csv(os.path.join(DATA_DIR, "chatter_summary.csv"))
    print(f"Saved attention: long={len(att_long)} rows, wide={att_wide.shape}")

    # 3) SEC FILINGS
    build_sec(cfg, tickers)

if __name__ == "__main__":
    main()