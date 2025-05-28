from duckduckgo_search import DDGS


def web_search(query: str, max_results: int = 3) -> list:
    """
    Perform a web search.

    Parameters
    -----
    query : str
        The query to web search
    max_results : int
        Number of results to retrieve (by default: 3)
    """
    if not query:
        raise ValueError("Search query cannot be empty")

    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=max_results)
        return [
            {"title": r["title"], "url": r["href"]}
            for r in results
            if "title" in r and "href" in r
        ]


if __name__ == "__main__":
    results = web_search("What is the capital of France?")
    print(results)
