import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (agentic-payments research agent)"}


def web_search(query: str, limit: int = 5) -> list[dict]:
    """Free general web search (DuckDuckGo). Returns title/url/snippet for
    each result. Use this for anything that doesn't need a specialized paid
    data source."""
    response = requests.post(SEARCH_URL, data={"q": query}, headers=_HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    results = []
    for result in soup.select(".result")[:limit]:
        link = result.select_one(".result__a")
        snippet = result.select_one(".result__snippet")
        if not link:
            continue
        results.append(
            {
                "title": link.get_text(strip=True),
                "url": link.get("href"),
                "snippet": snippet.get_text(strip=True) if snippet else "",
            }
        )
    return results
