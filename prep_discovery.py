import os
import math
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
UNIVERSE_PATH = DATA_DIR / "universe_today.csv"

def load_tickers():
    # Try to read existing tickers so we keep your universe
    if UNIVERSE_PATH.exists():
        try:
            df = pd.read_csv(UNIVERSE_PATH)
            if "ticker" in df.columns:
                tickers = sorted(set(str(t).strip().upper() for t in df["ticker"]))
                return tickers, df
        except Exception:
            pass
    # fallback starters if file was empty
    tickers = ["OPEN","AFRM","IREN","CIFR","CELH","OKTA","SNOW","GOOGL","QCOM","MDB"]
    return tickers, pd.DataFrame({"ticker": tickers})

def rsi(series, period=14):
    delta = series.diff()
    gain = (delta.clip(lower=0)).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def compute_for_ticker(ticker: str) -> dict:
    try:
        hist = yf.download(ticker, period="45d", interval="1d", progress=False)
        if hist.empty or len(hist) < 21:
            return {"ticker": ticker}

        hist = hist.dropna()
        hist["RSI14"] = rsi(hist["Close"], 14)

        today = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) >= 2 else None

        last_20 = hist.iloc[-21:-1] if len(hist) >= 21 else hist.iloc[:-1]
        avg20_vol = float(last_20["Volume"].mean()) if not last_20.empty else np.nan
        high20 = float(last_20["High"].max()) if not last_20.empty else np.nan

        vol_spike = float(today["Volume"]) / avg20_vol if avg20_vol and avg20_vol > 0 else np.nan
        breakout20 = int(float(today["High"]) > high20) if not math.isnan(high20) else np.nan

        rsi_cross_50 = np.nan
        if prev is not None and not math.isnan(today["RSI14"]) and not math.isnan(prev["RSI14"]):
            rsi_cross_50 = int(prev["RSI14"] <= 50 and today["RSI14"] > 50)

        pct_change = np.nan
        gap_up_5 = np.nan
        if prev is not None:
            pct_change = (float(today["Close"]) - float(prev["Close"])) / float(prev["Close"]) * 100.0
            gap_up_5 = int((float(today["Open"]) - float(prev["Close"])) / float(prev["Close"]) >= 0.05)

        return {
            "ticker": ticker,
            "last_close": round(float(today["Close"]), 4),
            "prev_close": round(float(prev["Close"]), 4) if prev is not None else np.nan,
            "open": round(float(today["Open"]), 4),
            "vol_spike": round(vol_spike, 2) if not math.isnan(vol_spike) else np.nan,
            "breakout20": breakout20,
            "rsi_cross_50": rsi_cross_50,
            "pct_change": round(pct_change, 2) if not math.isnan(pct_change) else np.nan,
            "gap_up_5": gap_up_5,
        }
    except Exception:
        return {"ticker": ticker}

def main():
    tickers, old = load_tickers()
    rows = [compute_for_ticker(t) for t in tickers]
    new = pd.DataFrame(rows)

    keep_cols = [c for c in ["ticker","score"] if c in old.columns]
    merged = new.merge(old[keep_cols].drop_duplicates(), on="ticker", how="left")

    cols = [
        "ticker","vol_spike","breakout20","rsi_cross_50","pct_change","gap_up_5",
        "last_close","prev_close","open","score"
    ]
    for c in cols:
        if c not in merged.columns:
            merged[c] = np.nan
    merged = merged[cols]

    UNIVERSE_PATH.parent.mkdir(exist_ok=True)
    merged.to_csv(UNIVERSE_PATH.as_posix(), index=False)
    print(f"Wrote {UNIVERSE_PATH} with {len(merged)} rows and columns: {list(merged.columns)}")

if __name__ == "__main__":
    main()