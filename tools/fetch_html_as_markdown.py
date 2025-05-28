import requests
from bs4 import BeautifulSoup
from markdownify import markdownify


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
    Fetch a web page and return it ain markdown format.

    This tool only works on HTML pages.

    Parameters
    ------
    url : str
        The URL to fetch, e.g.: https://example.org, https://example.org/path/to, https://example.org/path/to/file.html
    """
    response = requests.get(url, allow_redirects=True)
    content_type = response.headers.get("Content-Type", "")

    if "text/html" not in content_type:
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
