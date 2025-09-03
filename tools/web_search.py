import os
import time

import requests
from generative_ai_toolkit.agent import registry
from generative_ai_toolkit.context import AgentContext

from tools.registries import web_research


@registry.tool(tool_registry=web_research)
def web_search(query: str, max_results: int = 3, max_retries: int = 10) -> list:
    """
    Perform a web search using Brave Search for AI API.

    Parameters
    -----
    query : str
        The query to web search
    max_results : int
        Number of results to retrieve (by default: 3, max: 20)
    max_retries : int
        Number of times to retry, in case of rate limit errors (by default: 10)
    """

    if not query:
        raise ValueError("Search query cannot be empty")

    # Get API key from environment
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        raise ValueError("BRAVE_SEARCH_API_KEY environment variable not set")

    agent_context = AgentContext.current()
    current_trace = agent_context.tracer.current_trace
    stop_event = agent_context.stop_event

    # Ensure max_results doesn't exceed API limit
    max_results = min(max_results, 20)

    # API endpoint and headers
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "X-Subscription-Token": api_key,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }

    params = {
        "q": query,
        "count": max_results,
        "country": "us",
        "search_lang": "en",
        "safesearch": "moderate",
        "text_decorations": False,  # Disable to avoid HTML tags in results
    }

    for i in range(1 + max_retries):
        if stop_event and stop_event.is_set():
            raise RuntimeError("Aborted due to stop event")

        if i > 0:
            sleep_for = 1  # min(max(0.5, i * i * 0.25), 30)
            sleep_till = time.monotonic() + sleep_for
            current_trace.add_attribute("ai.tool.sleep.for", f"{sleep_for:.1f}")
            current_trace.emit_snapshot()
            while time.monotonic() < sleep_till:
                if stop_event and stop_event.is_set():
                    raise RuntimeError("Aborted due to stop event")
                time.sleep(0.1)

        response = requests.get(url, headers=headers, params=params, timeout=30)

        # Check for rate limiting (HTTP 429)
        if response.status_code == 429:
            current_trace.add_attribute("ai.tool.retries", i + 1)
            current_trace.emit_snapshot()
            continue

        # Raise exception for other HTTP errors
        response.raise_for_status()

        # Parse JSON response
        data = response.json()

        # Extract results
        results = []
        if "web" in data and "results" in data["web"]:
            for result in data["web"]["results"]:
                if "title" in result and "url" in result:
                    results.append({"title": result["title"], "url": result["url"]})

        return results

    # If we get here, we've exhausted all retries
    raise Exception("Max retries reached")


if __name__ == "__main__":
    # Set your API key as an environment variable before running
    # export BRAVE_SEARCH_API_KEY=your_api_key_here
    context = AgentContext.set_test_context()
    with context.tracer.trace("test") as trace:
        for _ in range(5):
            try:
                results = web_search("What is the capital of France?")
                print("Search Results:")
                for i, result in enumerate(results, 1):
                    print(f"{i}. {result['title']}")
                    print(f"   URL: {result['url']}")
                    print()
            except Exception as e:
                print(f"Error: {e}")
