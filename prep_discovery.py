import math
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
UNIVERSE_PATH = DATA_DIR / "universe_today.csv"

# ---------- helpers ----------
def _to_float(x):
    try:
        # handles pandas scalars/Series and numpy types
        if hasattr(x, "item"):
            return float(x.item())
        return float(x)
    except Exception:
        return np.nan

def rsi(series, period=14):
    delta = series.diff()
    gain = (delta.clip(lower=0)).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

# ---------- load universe tickers ----------
def load_universe():
    if UNIVERSE_PATH.exists():
        df = pd.read_csv(UNIVERSE_PATH)
        if "ticker" in df.columns:
            tickers = sorted(set(str(t).strip().upper() for t in df["ticker"]))
            return tickers, df
    # fallback if file missing
    tickers = ["OPEN","AFRM","IREN","CIFR","CELH","OKTA","SNOW","GOOGL","QCOM","MDB"]
    return tickers, pd.DataFrame({"ticker": tickers})

# ---------- compute signals for one ticker ----------
def compute_for_ticker(ticker: str) -> dict:
    try:
        # auto_adjust=False gives raw Open/High/Low/Close (so prev_close & open look proper)
        hist = yf.download(
            ticker, period="60d", interval="1d", auto_adjust=False, progress=False
        )
        if hist.empty or len(hist) < 21:
            return {"ticker": ticker}

        hist = hist.dropna()

        # Pre-compute RSI(14)
        hist["RSI14"] = rsi(hist["Close"], 14)

        today = hist.iloc[-1]
        prev = hist.iloc[-2]

        # 20-day window excludes today
        last_20 = hist.iloc[-21:-1]
        avg20_vol = _to_float(last_20["Volume"].mean())
        high20 = _to_float(last_20["High"].max())

        vol_today = _to_float(today["Volume"])
        high_today = _to_float(today["High"])
        open_today = _to_float(today["Open"])
        close_today = _to_float(today["Close"])
        close_prev = _to_float(prev["Close"])

        vol_spike = (vol_today / avg20_vol) if avg20_vol and avg20_vol > 0 else np.nan
        breakout20 = int(high_today > high20) if not math.isnan(high20) else np.nan

        rsi_today = _to_float(today["RSI14"])
        rsi_prev = _to_float(prev["RSI14"])
        rsi_cross_50 = (
            int(rsi_prev <= 50 and rsi_today > 50)
            if not math.isnan(rsi_today) and not math.isnan(rsi_prev)
            else np.nan
        )

        pct_change = (
            (close_today - close_prev) / close_prev * 100.0
            if close_prev and not math.isnan(close_prev)
            else np.nan
        )
        gap_up_5 = (
            int((open_today - close_prev) / close_prev >= 0.05)
            if close_prev and not math.isnan(close_prev)
            else np.nan
        )

        return {
            "ticker": ticker,
            "vol_spike": round(vol_spike, 2) if not math.isnan(vol_spike) else np.nan,
            "breakout20": breakout20,
            "rsi_cross_50": rsi_cross_50,
            "pct_change": round(pct_change, 2) if not math.isnan(pct_change) else np.nan,
            "gap_up_5": gap_up_5,
            "last_close": round(close_today, 4) if not math.isnan(close_today) else np.nan,
            "prev_close": round(close_prev, 4) if not math.isnan(close_prev) else np.nan,
            "open": round(open_today, 4) if not math.isnan(open_today) else np.nan,
        }
    except Exception:
        return {"ticker": ticker}

# ---------- main ----------
def main():
    tickers, old = load_universe()

    # ALWAYS compute for every ticker already in the CSV
    rows = [compute_for_ticker(t) for t in tickers]
    new = pd.DataFrame(rows)

    # carry through any existing columns like score, news_sentiment if present
    keep_cols = [c for c in ["ticker","score","news_sentiment"] if c in old.columns]
    merged = new.merge(old[keep_cols].drop_duplicates(), on="ticker", how="left")

    # final column order
    cols = [
        "ticker","vol_spike","breakout20","rsi_cross_50","pct_change","gap_up_5",
        "last_close","prev_close","open","score","news_sentiment"
    ]
    for c in cols:
        if c not in merged.columns:
            merged[c] = np.nan
    merged = merged[cols]

    UNIVERSE_PATH.parent.mkdir(exist_ok=True)
    merged.to_csv(UNIVERSE_PATH.as_posix(), index=False)
    print(f"Wrote {UNIVERSE_PATH} with {len(merged)} rows.")

if __name__ == "__main__":
    main()