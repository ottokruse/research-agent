import pathlib
from typing import Any

from generative_ai_toolkit.agent import registry
from pypdf import PdfReader

BASE_DIR = pathlib.Path.cwd().resolve()


def _resolve_path(path: str) -> pathlib.Path:
    """
    Resolve a path safely relative to the base directory and prevent path traversal.

    Parameters
    -----
    path : str
        The relative or absolute path to resolve
    """
    abs_path = (BASE_DIR / path).resolve()
    if not str(abs_path).startswith(str(BASE_DIR)):
        raise PermissionError("Access outside of the working directory is not allowed")
    return abs_path


@registry.tool
def read_pdf(path: str, page_range: str | None = None) -> dict[str, Any]:
    """
    Read a PDF file from the local filesystem and extract text content.

    Parameters
    -----
    path : str
        The path to the PDF file, relative to the current working directory
    page_range : str, optional
        Page range to extract (e.g., "1-5", "3", "1,3,5-7"). If not specified, extracts all pages.
    """
    if not path:
        raise ValueError("File path cannot be empty")

    abs_path = _resolve_path(path)

    if not abs_path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if not abs_path.suffix.lower() == ".pdf":
        raise ValueError(f"File is not a PDF: {path}")

    try:
        reader = PdfReader(str(abs_path))

        # Extract metadata
        metadata = {}
        if reader.metadata:
            metadata = {
                "title": reader.metadata.get("/Title", ""),
                "author": reader.metadata.get("/Author", ""),
                "subject": reader.metadata.get("/Subject", ""),
                "creator": reader.metadata.get("/Creator", ""),
                "producer": reader.metadata.get("/Producer", ""),
                "creation_date": str(reader.metadata.get("/CreationDate", "")),
                "modification_date": str(reader.metadata.get("/ModDate", "")),
            }

        total_pages = len(reader.pages)

        # Parse page range if provided
        pages_to_extract = None
        if page_range:
            pages_to_extract = _parse_page_range(page_range, total_pages)
        else:
            pages_to_extract = list(range(total_pages))

        # Extract text from specified pages
        page_texts = []
        all_text = []

        for page_num in pages_to_extract:
            if 0 <= page_num < total_pages:
                page = reader.pages[page_num]
                page_text = page.extract_text()
                page_texts.append(
                    {
                        "page_number": page_num + 1,  # 1-indexed for user display
                        "text": page_text,
                    }
                )
                all_text.append(page_text)

        return {
            "text": "\n\n".join(all_text),
            "pages": page_texts,
            "metadata": metadata,
            "page_count": total_pages,
            "extracted_pages": len(page_texts),
        }

    except Exception as e:
        raise RuntimeError(f"Error reading PDF file: {str(e)}")


def _parse_page_range(page_range: str, total_pages: int) -> list[int]:
    """
    Parse a page range string and return a list of 0-indexed page numbers.

    Parameters
    -----
    page_range : str
        Page range string (e.g., "1-5", "3", "1,3,5-7")
    total_pages : int
        Total number of pages in the PDF

    Returns
    -----
    List[int]
        List of 0-indexed page numbers
    """
    pages = set()

    # Split by comma to handle multiple ranges/numbers
    parts = [part.strip() for part in page_range.split(",")]

    for part in parts:
        if "-" in part:
            # Handle range (e.g., "1-5")
            try:
                start, end = part.split("-", 1)
                start_page = int(start.strip()) - 1  # Convert to 0-indexed
                end_page = int(end.strip()) - 1  # Convert to 0-indexed

                # Validate range
                start_page = max(0, min(start_page, total_pages - 1))
                end_page = max(0, min(end_page, total_pages - 1))

                if start_page <= end_page:
                    pages.update(range(start_page, end_page + 1))
            except ValueError:
                raise ValueError(f"Invalid page range format: {part}")
        else:
            # Handle single page number
            try:
                page_num = int(part.strip()) - 1  # Convert to 0-indexed
                if 0 <= page_num < total_pages:
                    pages.add(page_num)
            except ValueError:
                raise ValueError(f"Invalid page number: {part}")

    return sorted(list(pages))
