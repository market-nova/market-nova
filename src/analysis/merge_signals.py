# src/analysis/merge_signals.py
import pandas as pd
from typing import Optional  # <-- added for Python 3.9

def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / (s.std(ddof=0) + 1e-9)

# Rewritten signature for Python 3.9 (no "|" union types)
def merge_and_score(news_df: pd.DataFrame, x_counts_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    # Roll up news sentiment per ticker
    by_ticker = news_df.groupby("ticker")["sentiment"].mean().rename("news_sentiment")
    out = by_ticker.to_frame()

    if x_counts_df is not None and not x_counts_df.empty:
        # Expect columns: ticker, count, change
        x_roll = x_counts_df.groupby("ticker")["change"].mean().rename("x_chatter_change")
        out = out.join(x_roll, how="left")
    else:
        out["x_chatter_change"] = 0.0

    # Simple composite score (standardize components so they are comparable)
    out["score"] = zscore(out["news_sentiment"].fillna(0)) * 0.6 + zscore(out["x_chatter_change"].fillna(0)) * 0.4
    return out.reset_index()