"""DuckDuckGo web search helper for StudyBoost AI."""
from __future__ import annotations

from duckduckgo_search import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Run a DuckDuckGo search (no API key) and return a list of results."""
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, region="fr-fr", max_results=max_results):
                results.append({
                    "title": r.get("title", "Sans titre"),
                    "href": r.get("href", ""),
                    "body": r.get("body", ""),
                })
    except Exception:
        return []
    return results


def format_results(results: list[dict[str, str]]) -> str:
    """Format search results as Markdown."""
    if not results:
        return "Aucun résultat de recherche trouvé."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. [{r['title']}]({r['href']})\n{r['body'][:300]}"
        )
    return "\n\n".join(lines)
