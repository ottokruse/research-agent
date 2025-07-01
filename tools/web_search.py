import time

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from generative_ai_toolkit.agent import registry


@registry.tool
def web_search(query: str, max_results: int = 3, max_retries: int = 5) -> list:
    """
    Perform a web search.

    Parameters
    -----
    query : str
        The query to web search
    max_results : int
        Number of results to retrieve (by default: 3)
    max_retries : int
        Number of times to retry, in case of rate limit errors (by default: 5)
    """
    if not query:
        raise ValueError("Search query cannot be empty")

    with DDGS() as ddgs:
        for i in range(1 + max_retries):
            try:
                results = ddgs.text(query, max_results=max_results)
            except DuckDuckGoSearchException as err:
                if "rate" in str(err).lower() and i < max_retries:
                    time.sleep(max(1, i * i * 0.25))
                    continue
                raise
            return [
                {"title": r["title"], "url": r["href"]}
                for r in results
                if "title" in r and "href" in r
            ]
        else:
            raise Exception("Max retries reached")


if __name__ == "__main__":
    results = web_search("What is the capital of France?")
    print(results)
