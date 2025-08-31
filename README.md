
# Market Pulse - DIY SEC + News + X Sentiment

A minimal, local-first toolkit to monitor SEC filings, news, and X chatter for a quick market pulse.

## What it does
- Pulls recent SEC filings for tickers and highlights language changes vs prior filing
- Monitors news via RSS and scores headline sentiment
- Optionally tracks X mentions volume and sentiment (if you add API keys)
- Merges signals into a simple daily score and shows a Streamlit dashboard

## Quick start
1) **Python 3.10+** recommended. Create a virtualenv:
```
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

2) Install deps:
```
pip install -r requirements.txt
```

3) Copy config and add your secrets:
```
cp config.example.toml config.toml
# edit config.toml with your tickers and optional API keys
```

4) Run a one-shot pull + score:
```
python run_once.py
```

5) Launch dashboard:
```
streamlit run app.py
```

## Notes
- SEC: uses the EDGAR submissions API with proper User-Agent header per SEC guidance.
- News: uses Google News RSS feeds per ticker.
- X: requires an X API key (or comment out that module). If you prefer, swap to Reddit/Bluesky.
- Sentiment: defaults to FinBERT; auto-falls back to VADER if Transformers not available.
- LLM assist: You can plug in OpenAI or Claude for summaries in `nlp/summarize.py`.

## Claude vs building yourself
- **DIY**: maximum control, transparent features, low variable cost, some setup work.
- **Claude/OpenAI only**: fastest way to summarize/diff filings and headlines, but you pay per token and rely on a third-party API.
- Best of both: run this pipeline locally and call an LLM only for the hardest summaries.



## Daily Universe (50 tickers) - Gainers + Volume Spikes
1) Edit `data/universe_base.csv` to include all tickers you want considered.
2) Build today's 50-ticker universe (gainers + volume spikes):
```
python seed_universe.py
```
3) Pull news/sentiment and merge:
```
python run_once.py
```
4) Launch the UI:
```
streamlit run app_pro.py
```

Notes:
- The seeder ranks by a blend of last-day % change and volume spike vs the 20-day average.
- Change `[universe].size` in `config.toml` if you want 30/100/etc instead of 50.
