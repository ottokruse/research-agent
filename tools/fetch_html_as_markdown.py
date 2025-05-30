import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

# Global session object to maintain cookies across requests
_session = requests.Session()


def _clean_html(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Remove <script> and <style> tags
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Optionally, remove inline JS event handlers (like onclick)
    for tag in soup.find_all():
        for attr in list(tag.attrs):
            if attr.lower().startswith("on"):
                del tag.attrs[attr]

    clean_html = str(soup)
    return clean_html


def fetch_html_as_markdown(url: str) -> str:
    """
    Fetch a web page and return it in markdown format.

    This tool works on HTML and XHTML pages.

    Parameters
    ------
    url : str
        The URL to fetch, e.g.: https://example.org, https://example.org/path/to, https://example.org/path/to/file.html
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

    # Use the session object to maintain cookies across requests
    response = _session.get(url, headers=headers, allow_redirects=True)
    content_type = response.headers.get("Content-Type", "")

    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise ValueError(f"Unsupported content type: {content_type}")

    html_content = response.text
    markdown_content = markdownify(
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
        ],
        images_inline=False,
    )

    return markdown_content
