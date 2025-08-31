
import os
import time
import json
import re
import requests
from pathlib import Path

try:
    import tomllib  # Py3.11+
except ModuleNotFoundError:  # Py3.10
    import tomli as tomllib

BASE = "https://data.sec.gov/submissions/CIK{cik}.json"
HEADERS = {}

def load_cfg(cfg_path="config.toml"):
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)

def _ensure_headers(user_agent: str):
    global HEADERS
    if not HEADERS:
        HEADERS = {"User-Agent": user_agent, "Accept-Encoding": "gzip", "Host": "data.sec.gov"}

def cik_from_ticker(ticker: str) -> str:
    # SEC publishes mapping here: https://www.sec.gov/files/company_tickers.json
    # For simplicity, use a cached copy if present or pull once.
    cache = Path("data/sec/company_tickers.json")
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        data = json.loads(cache.read_text())
    else:
        url = "https://www.sec.gov/files/company_tickers.json"
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        cache.write_text(json.dumps(data))
        time.sleep(0.25)
    for _, row in data.items():
        if row.get("ticker", "").upper() == ticker.upper():
            return str(row["cik_str"]).zfill(10)
    raise ValueError(f"CIK not found for {ticker}")

def fetch_recent_filings(cik: str, user_agent: str):
    _ensure_headers(user_agent)
    url = BASE.format(cik=cik)
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def latest_10x_text_url(sub_json, form_types=("10-K","10-Q")):
    filings = sub_json.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    docs = filings.get("primaryDocument", [])
    bases = filings.get("primaryDocDescription", [])
    accession = filings.get("accessionNumber", [])
    for i, f in enumerate(forms):
        if f in form_types:
            acc = accession[i].replace("-", "")
            doc = docs[i]
            # construct URL to full text
            return f"https://www.sec.gov/ixviewer/doc?action=display&source=content&doc=/Archives/edgar/data/{int(sub_json['cik']):d}/{acc}/{doc}"
    return None

def save_text(url: str, out_path: Path, user_agent: str):
    _ensure_headers(user_agent)
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    out_path.write_text(r.text, encoding="utf-8")

def strip_html(text: str) -> str:
    # naive cleanup
    return re.sub("<[^>]+>", " ", text)

def main(cfg_path="config.toml"):
    cfg = load_cfg(cfg_path)
    ua = cfg["sec"]["user_agent"]
    out_dir = Path(cfg["sec"].get("cache_dir", "data/sec"))
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for t in cfg["tickers"]:
        try:
            cik = cik_from_ticker(t)
            sub = fetch_recent_filings(cik, ua)
            url = latest_10x_text_url(sub)
            if url:
                raw_path = out_dir / f"{t}_latest.html"
                save_text(url, raw_path, ua)
                clean = strip_html(raw_path.read_text(encoding="utf-8"))
                (out_dir / f"{t}_latest.txt").write_text(clean, encoding="utf-8")
                results.append({"ticker": t, "cik": cik, "url": url, "saved": True})
            else:
                results.append({"ticker": t, "cik": cik, "url": None, "saved": False})
            time.sleep(0.5)
        except Exception as e:
            results.append({"ticker": t, "error": str(e)})
    return results

if __name__ == "__main__":
    print(main())
