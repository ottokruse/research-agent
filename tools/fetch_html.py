import functools
import re

import requests
from bs4 import BeautifulSoup
from generative_ai_toolkit.agent import registry
from generative_ai_toolkit.context import AgentContext
from markdownify import markdownify

from tools.registries import web_research


@functools.lru_cache(25)
def get_session(principal_id: str, conversation_id: str):
    return requests.Session()


def _clean_html(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Remove <script> and <style> tags
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Optionally, remove inline JS event handlers (like onclick)
    for tag in soup.find_all():
        for attr in list(tag.attrs):  # type: ignore
            if attr.lower().startswith("on"):
                del tag.attrs[attr]  # type: ignore

    clean_html = str(soup)
    return clean_html


@registry.tool(tool_registry=web_research)
def fetch_html(url: str, page: int = 1, format: str = "md"):
    """
    Fetch a web page and return it in either markdown (default) or raw HTML format.

    Output will be truncated to max 10,000 characters.

    This tool works on HTML and XHTML pages.

    Parameters
    ------
    url : str
        The URL to fetch, e.g.: https://example.org, https://example.org/path/to, https://example.org/path/to/file.html
    page : int
        The next page nr to request, in case the previous request was truncated.
    format : str, optional
        The return format, either "md" or "html", default "md"
    """
    # Add comprehensive browser-like headers to avoid bot detection
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",  # Do Not Track
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    }

    context = AgentContext.current()
    try:

        session = get_session(
            context.auth_context["principal_id"], context.conversation_id
        )
        response = session.get(url, headers=headers, allow_redirects=True, timeout=30.0)
        content_type = response.headers.get("Content-Type", "")

        # Improved content type checking - use regex to match base content type
        if not (
            re.search(r"text/html", content_type, re.I)
            or re.search(r"application/xhtml\+xml", content_type, re.I)
        ):
            return f"Error: Unsupported content type: {content_type}. Cannot convert to markdown."

        # Check if response content appears to be binary/non-text
        try:
            # Try to decode a sample of the content to check if it's text
            sample = response.content[:1000]
            sample.decode(response.encoding or "utf-8")
        except UnicodeDecodeError:
            return "Error: Content appears to be binary data, not text/HTML. Cannot convert to markdown."

        # Get the text content with proper encoding
        html_content = response.text

        # Check if content is actually HTML (basic validation)
        if not re.search(r"<html|<body|<div|<p|<h[1-6]|<!DOCTYPE", html_content, re.I):
            return "Error: Content doesn't appear to be valid HTML. Cannot convert to markdown."

        if format == "md":

            content = markdownify(
                _clean_html(html_content),
                convert=[
                    "a",
                    "p",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "ul",
                    "ol",
                    "li",
                    "strong",
                    "em",
                    "blockquote",
                    "img",
                ],
            )

        else:
            content = html_content

        if len(content) <= 10_000:
            return content

        start_pos = (page - 1) * 10_000
        return (
            content[start_pos : start_pos + 10_000]
            + f"\n\n[... truncated, next page: {page + 1} ...]"
        )
    except Exception as e:
        return f"Error fetching or processing URL: {str(e)}"
