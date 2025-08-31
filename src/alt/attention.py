# src/alt/attention.py — ALL SIX SOURCES + 1h cache + 1–100 scoring (Python 3.9 OK)

from __future__ import annotations
import os, json, time, math, datetime as dt
from typing import List, Dict, Any
from urllib.parse import urlencode, urlparse
import pandas as pd

# Optional libs (we degrade gracefully if missing)
try:
    from pytrends.request import TrendReq
    HAS_TRENDS = True
except Exception:
    HAS_TRENDS = False

try:
    import feedparser
    HAS_FEED = True
except Exception:
    HAS_FEED = False

try:
    import requests
    HAS_REQ = True
except Exception:
    HAS_REQ = False

try:
    import praw  # Reddit official API (optional)
    HAS_PRAW = True
except Exception:
    HAS_PRAW = False


# --------------------------- tiny JSON cache ---------------------------
CACHE_DIR = "data/.cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_path(key: str) -> str:
    safe = key.replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_").replace(" ", "_")
    return os.path.join(CACHE_DIR, f"{safe}.json")

def _load_cache(key: str, ttl_seconds: int):
    p = _cache_path(key)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            blob = json.load(f)
        if time.time() - blob.get("_ts", 0) <= ttl_seconds:
            return blob.get("payload")
    except Exception:
        return None
    return None

def _save_cache(key: str, payload):
    try:
        with open(_cache_path(key), "w", encoding="utf-8") as f:
            json.dump({"_ts": time.time(), "payload": payload}, f)
    except Exception:
        pass

def _domain(u: str) -> str:
    try:
        return urlparse(u).netloc.replace("www.", "")
    except Exception:
        return ""


# --------------------------- providers ---------------------------

def get_trends(tickers: List[str], days: int = 7, geo: str = "US",
               max_keywords: int = 10, ttl: int = 3600, force_refresh: bool = False) -> pd.DataFrame:
    """Google Trends average interest and % change over the window."""
    if not HAS_TRENDS or not tickers:
        return pd.DataFrame()
    key = f"trends_{','.join(tickers[:max_keywords])}_{days}_{geo}"
    if not force_refresh:
        cached = _load_cache(key, ttl)
        if cached is not None:
            return pd.DataFrame(cached)

    kw = [f"{t.upper()} stock" for t in tickers[:max_keywords]]
    rows = []
    try:
        py = TrendReq(hl="en-US", tz=360)
        py.build_payload(kw, timeframe=f"now {days}-d", geo=geo)
        df = py.interest_over_time()
        if not df.empty and "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])
        for t, col in zip(tickers[:max_keywords], kw):
            if col in df.columns:
                s = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
                if len(s) == 0:
                    continue
                first, last = float(s.iloc[0]), float(s.iloc[-1])
                chg = ((last - first) / first * 100.0) if first > 0 else 0.0
                rows.append({"ticker": t.upper(), "source": "trends",
                             "value": round(float(s.mean()), 2), "change_pct": round(chg, 1)})
    except Exception:
        pass

    out = pd.DataFrame(rows)
    _save_cache(key, out.to_dict(orient="records"))
    return out


def get_reddit_rss(tickers: List[str], lookback_days: int = 7,
                   ttl: int = 3600, force_refresh: bool = False) -> pd.DataFrame:
    """Counts posts from Reddit RSS search for last 24h vs prior window."""
    if not HAS_FEED or not tickers:
        return pd.DataFrame()
    key = f"reddit_rss_{','.join(tickers)}_{lookback_days}"
    if not force_refresh:
        cached = _load_cache(key, ttl)
        if cached is not None:
            return pd.DataFrame(cached)

    now = dt.datetime.utcnow()
    day_ago = now - dt.timedelta(days=1)
    prior_start = now - dt.timedelta(days=lookback_days)
    rows = []
    for t in tickers:
        t = t.upper()
        hits_24h, hits_prior = 0, 0
        seen = set()
        for url in (f"https://www.reddit.com/search.rss?q=%24{t}&sort=new",
                    f"https://www.reddit.com/search.rss?q={t}&sort=new"):
            try:
                feed = feedparser.parse(url, agent="MarketPulsePro/1.0")
            except Exception:
                continue
            for e in getattr(feed, "entries", []):
                link = getattr(e, "link", "")
                if link in seen:
                    continue
                seen.add(link)
                stamp = getattr(e, "published_parsed", None)
                if not stamp:
                    continue
                ts = dt.datetime.fromtimestamp(time.mktime(stamp))
                if ts >= day_ago:
                    hits_24h += 1
                elif prior_start <= ts < day_ago:
                    hits_prior += 1
        avg_prior = hits_prior / max(1, (lookback_days - 1))
        chg = ((hits_24h - avg_prior) / avg_prior * 100.0) if avg_prior > 0 else (100.0 if hits_24h > 0 else 0.0)
        rows.append({"ticker": t, "source": "reddit_rss",
                     "value": int(hits_24h), "change_pct": round(chg, 1)})

    out = pd.DataFrame(rows)
    _save_cache(key, out.to_dict(orient="records"))
    return out


def get_reddit_api(tickers: List[str], cfg: Dict[str, Any], hours: int = 24,
                   ttl: int = 3600, force_refresh: bool = False) -> pd.DataFrame:
    """
    Uses Reddit official API via PRAW if credentials exist under [reddit] in config.toml:
      client_id, client_secret, user_agent
    Counts posts in r/all since <hours>.
    """
    if not HAS_PRAW or not tickers:
        return pd.DataFrame()
    need = ("client_id" in cfg and "client_secret" in cfg and "user_agent" in cfg)
    if not need:
        return pd.DataFrame()

    key = f"reddit_api_{','.join(tickers)}_{hours}"
    if not force_refresh:
        cached = _load_cache(key, ttl)
        if cached is not None:
            return pd.DataFrame(cached)

    try:
        reddit = praw.Reddit(
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
            user_agent=cfg["user_agent"],
            check_for_async=False,
        )
    except Exception:
        return pd.DataFrame()

    since = time.time() - hours * 3600
    rows = []
    for t in tickers:
        q = f'${t} OR {t}'
        count = 0
        try:
            for sub in reddit.subreddit("all").search(q, sort="new", limit=200, time_filter="day"):
                if getattr(sub, "created_utc", 0) >= since:
                    count += 1
        except Exception:
            pass
        rows.append({"ticker": t.upper(), "source": "reddit_api",
                     "value": int(count), "change_pct": float(count)})

    out = pd.DataFrame(rows)
    _save_cache(key, out.to_dict(orient="records"))
    return out


def get_stocktwits(tickers: List[str], ttl: int = 3600, force_refresh: bool = False) -> pd.DataFrame:
    """Counts first-page messages for each symbol (proxy for chatter)."""
    if not HAS_REQ or not tickers:
        return pd.DataFrame()
    rows = []
    for t in tickers:
        key = f"stocktwits_{t}"
        if not force_refresh:
            cached = _load_cache(key, ttl)
            if cached is not None:
                rows.append(cached); continue
        payload = {"ticker": t.upper(), "source": "stocktwits", "value": 0, "change_pct": 0.0}
        try:
            r = requests.get(f"https://api.stocktwits.com/api/2/streams/symbol/{t}.json", timeout=20)
            if r.ok:
                msgs = r.json().get("messages", [])
                payload["value"] = len(msgs)
                payload["change_pct"] = float(len(msgs))
        except Exception:
            pass
        rows.append(payload)
        _save_cache(key, payload)
    return pd.DataFrame(rows)


def get_gdelt(tickers: List[str], hours: int = 24,
              ttl: int = 3600, force_refresh: bool = False) -> pd.DataFrame:
    """Counts GDELT article hits for the last N hours."""
    if not HAS_REQ or not tickers:
        return pd.DataFrame()
    rows = []
    start = (dt.datetime.utcnow() - dt.timedelta(hours=hours)).strftime("%Y%m%d%H%M%S")
    for t in tickers:
        key = f"gdelt_{t}_{hours}"
        if not force_refresh:
            cached = _load_cache(key, ttl)
            if cached is not None:
                rows.append(cached); continue
        payload = {"ticker": t.upper(), "source": "gdelt", "value": 0, "change_pct": 0.0}
        try:
            url = "https://api.gdeltproject.org/api/v2/doc/doc"
            params = {"query": t, "mode": "ArtList", "maxrecords": 250, "format": "JSON",
                      "startdatetime": start}
            r = requests.get(url, params=params, timeout=20)
            if r.ok:
                arts = r.json().get("articles", [])
                payload["value"] = len(arts)
                payload["change_pct"] = float(len(arts))
        except Exception:
            pass
        rows.append(payload)
        _save_cache(key, payload)
    return pd.DataFrame(rows)


def get_wiki(tickers: List[str], days: int = 7,
             ttl: int = 3600, force_refresh: bool = False) -> pd.DataFrame:
    """Approximates company pages via search; aggregates pageviews over last N days."""
    if not HAS_REQ or not tickers:
        return pd.DataFrame()
    sess = requests.Session()
    end = dt.datetime.utcnow().strftime("%Y%m%d")
    start = (dt.datetime.utcnow() - dt.timedelta(days=days)).strftime("%Y%m%d")
    rows = []
    for t in tickers[:30]:  # cap politely
        key = f"wiki_{t}_{days}"
        if not force_refresh:
            cached = _load_cache(key, ttl)
            if cached is not None:
                rows.append(cached); continue
        payload = {"ticker": t.upper(), "source": "wiki", "value": 0, "change_pct": 0.0}
        try:
            s = sess.get("https://en.wikipedia.org/w/api.php",
                         params={"action": "query", "list": "search", "srsearch": t, "format": "json", "srlimit": 1},
                         timeout=20).json()
            hits = s.get("query", {}).get("search", [])
            if not hits:
                rows.append(payload); _save_cache(key, payload); continue
            title = hits[0]["title"]
            pv = sess.get(
                f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/{title}/daily/{start}/{end}",
                timeout=20
            )
            if pv.ok:
                items = pv.json().get("items", [])
                vals = [int(it.get("views", 0)) for it in items]
                if vals:
                    first, last = vals[0], vals[-1]
                    chg = ((last - first) / first * 100.0) if first > 0 else 0.0
                    payload["value"] = int(sum(vals))
                    payload["change_pct"] = round(chg, 1)
        except Exception:
            pass
        rows.append(payload)
        _save_cache(key, payload)
    return pd.DataFrame(rows)


# --------------------------- aggregate + scale 1–100 ---------------------------

def _minmax_1_100(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if s.nunique(dropna=True) <= 1:
        return pd.Series([50] * len(s), index=s.index, dtype=int)
    vmin, vmax = float(s.min()), float(s.max())
    scaled = 1 + ((s - vmin) / (vmax - vmin) * 99.0).round()
    return scaled.astype(int).clip(1, 100)

def _score_metric(df: pd.DataFrame) -> pd.Series:
    # Prefer change_pct when present (captures spikes), else raw value
    if "change_pct" in df and pd.to_numeric(df["change_pct"], errors="coerce").abs().sum() > 0:
        return pd.to_numeric(df["change_pct"], errors="coerce").fillna(0.0).abs()
    return pd.to_numeric(df.get("value", 0), errors="coerce").fillna(0.0)

def aggregate_attention(tickers: List[str], cfg: Dict[str, Any] = None,
                        ttl: int = 3600, force_refresh: bool = False) -> pd.DataFrame:
    """
    Returns a long-form DataFrame:
      ticker | source | value | change_pct | score_100
    where score_100 is a per-source min–max scaled 1..100 (using change_pct when available).
    """
    tickers = [str(t).upper() for t in tickers]
    cfg = cfg or {}

    frames: List[pd.DataFrame] = []

    try:
        frames.append(get_trends(tickers, ttl=ttl, force_refresh=force_refresh))
    except Exception:
        pass
    try:
        frames.append(get_reddit_rss(tickers, ttl=ttl, force_refresh=force_refresh))
    except Exception:
        pass
    try:
        rcfg = cfg.get("reddit", {})
        frames.append(get_reddit_api(tickers, rcfg, ttl=ttl, force_refresh=force_refresh))
    except Exception:
        pass
    try:
        frames.append(get_stocktwits(tickers, ttl=ttl, force_refresh=force_refresh))
    except Exception:
        pass
    try:
        frames.append(get_gdelt(tickers, ttl=ttl, force_refresh=force_refresh))
    except Exception:
        pass
    try:
        frames.append(get_wiki(tickers, ttl=ttl, force_refresh=force_refresh))
    except Exception:
        pass

    frames = [f for f in frames if isinstance(f, pd.DataFrame) and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["ticker", "source", "value", "change_pct", "score_100"])

    long_df = pd.concat(frames, ignore_index=True)
    # Compute per-source 1–100 scores
    long_df["metric"] = long_df.groupby("source", group_keys=False).apply(lambda d: _score_metric(d))
    long_df["score_100"] = long_df.groupby("source")["metric"].transform(_minmax_1_100)
    long_df = long_df.drop(columns=["metric"])
    # Ensure types
    if "value" in long_df:
        long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce").fillna(0).astype(float)
    if "change_pct" in long_df:
        long_df["change_pct"] = pd.to_numeric(long_df["change_pct"], errors="coerce").fillna(0).astype(float)
    long_df["score_100"] = pd.to_numeric(long_df["score_100"], errors="coerce").fillna(1).astype(int)
    return long_df