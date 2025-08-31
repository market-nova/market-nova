
import feedparser
from urllib.parse import quote_plus

def google_news_rss(query: str) -> str:
    # English news, sorted by relevance
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"

def fetch_headlines_for_ticker(ticker: str, limit: int = 20):
    url = google_news_rss(f"{ticker} stock OR {ticker} company")
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:limit]:
        items.append({"ticker": ticker, "title": entry.title, "link": entry.link, "published": getattr(entry, "published", "")})
    return items
