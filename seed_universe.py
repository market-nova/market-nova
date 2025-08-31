
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:
    import tomli as tomllib

def load_cfg(path="config.toml"):
    try:
        with open(path,"rb") as f:
            return tomllib.load(f)
    except Exception:
        return {"universe":{"size":50}}

def fetch_prices(tickers, days=60):
    end = datetime.today()
    start = end - timedelta(days=days+10)
    data = yf.download(tickers, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), auto_adjust=True, progress=False, group_by='ticker')
    out = {}
    for t in tickers:
        df = data[t].copy() if isinstance(data.columns, pd.MultiIndex) else data.copy()
        df = df.rename(columns=str.title)
        out[t] = df
    return out

def score_one(df: pd.DataFrame) -> float:
    if len(df) < 25:
        return -np.inf
    # last day values
    vol20 = df["Volume"].rolling(20).mean()
    vol_spike = (df["Volume"] / (vol20 + 1e-9)).iloc[-1]
    pct = df["Close"].pct_change().iloc[-1]
    # composite heuristic
    return float(0.6 * np.tanh(pct*10) + 0.4 * np.tanh((vol_spike-1)))

def main():
    base = pd.read_csv("data/universe_base.csv")
    tickers = base["ticker"].dropna().astype(str).str.upper().unique().tolist()
    cfg = load_cfg()
    size = int(cfg.get("universe", {}).get("size", 50))

    prices = fetch_prices(tickers, days=60)
    rows = []
    for t, df in prices.items():
        try:
            score = score_one(df)
            last_close = float(df["Close"].iloc[-1]) if len(df) else np.nan
            rows.append({"ticker": t, "score": score, "last_close": last_close})
        except Exception:
            rows.append({"ticker": t, "score": -np.inf, "last_close": np.nan})
    df = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).dropna(subset=["score"])
    df = df.sort_values("score", ascending=False).head(size).reset_index(drop=True)
    df.to_csv("data/universe_today.csv", index=False)
    print(df.head(10))
    print(f"Saved {len(df)} tickers to data/universe_today.csv")

if __name__ == "__main__":
    main()
