# src/discovery/screener.py  (Py3.9 friendly)
from typing import List, Optional, Dict
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def fetch_ohlcv(tickers: List[str], lookback_days: int = 60) -> Dict[str, pd.DataFrame]:
    end = datetime.today()
    start = end - timedelta(days=lookback_days + 10)
    data = yf.download(
        tickers, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"),
        auto_adjust=True, progress=False, group_by='ticker'
    )
    out: Dict[str, pd.DataFrame] = {}
    if isinstance(tickers, str):
        tickers = [tickers]
    for t in tickers:
        df = data[t].copy() if isinstance(data.columns, pd.MultiIndex) else data.copy()
        df = df.rename(columns=str.title)
        df["Ticker"] = t
        out[t] = df
    return out

def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Vol20"] = df["Volume"].rolling(20).mean()
    df["VolSpike"] = df["Volume"] / (df["Vol20"] + 1e-9)
    df["High20"] = df["High"].rolling(20).max()
    df["Breakout20"] = (df["Close"] > df["High20"].shift(1)).astype(int)
    df["RSI14"] = rsi(df["Close"], 14)
    df["RSI_Cross_50"] = ((df["RSI14"] > 50) & (df["RSI14"].shift(1) <= 50)).astype(int)
    df["PctChange"] = df["Close"].pct_change()
    df["GapUp5"] = ((df["Open"] > df["Close"].shift(1) * 1.05)).astype(int)
    return df

def screen(tickers: List[str], sentiment_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    data = fetch_ohlcv(tickers)
    rows = []
    for t, df in data.items():
        if len(df) < 30:
            continue
        sig = compute_signals(df).iloc[-1]
        vol_spike = float(sig["VolSpike"]) if np.isfinite(sig["VolSpike"]) else 0.0
        breakout = int(sig["Breakout20"])
        rsi_cross = int(sig["RSI_Cross_50"])
        pct = float(sig["PctChange"])
        gap = int(sig["GapUp5"])
        rows.append({
            "ticker": t, "vol_spike": vol_spike, "breakout20": breakout,
            "rsi_cross_50": rsi_cross, "pct_change": pct, "gap_up_5": gap
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Merge sentiment if provided
    if sentiment_df is not None and not sentiment_df.empty:
        s = sentiment_df.groupby("ticker")["sentiment"].mean().rename("news_sentiment")
        out = out.merge(s.reset_index(), on="ticker", how="left")
    else:
        out["news_sentiment"] = 0.0
    # Composite discovery score
    out["discovery_score"] = (
        (out["vol_spike"].clip(0, 10) / 10.0) * 0.45 +
        out["breakout20"] * 0.25 +
        out["rsi_cross_50"] * 0.15 +
        (out["news_sentiment"].fillna(0).clip(-1, 1) + 1) / 2 * 0.15
    )
    return out.sort_values("discovery_score", ascending=False).reset_index(drop=True)