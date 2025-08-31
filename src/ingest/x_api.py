
import os
import requests

def search_recent_counts(query: str, bearer_token: str, granularity="hour"):
    # X API v2 recent counts endpoint (Academic/Pro may differ). Adjust per your plan.
    url = "https://api.twitter.com/2/tweets/counts/recent"
    params = {"query": query, "granularity": granularity}
    headers = {"Authorization": f"Bearer {bearer_token}"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    if r.status_code == 401:
        raise RuntimeError("Unauthorized - check X bearer token or API plan")
    r.raise_for_status()
    return r.json()
