from pathlib import Path

from bs4 import BeautifulSoup

from .html_ops import (
    bold_li_prefix_before_colon,
    listify_numbered_paragraphs,
    normalize_strong_spacing,
    promote_short_paragraphs_to_h2,
    strip_empty_paragraphs,
)

__all__ = ["format_html"]


def format_html(input_file: Path, output_file: Path, heading_length: int = 64) -> None:
    """Normalize numbered paragraphs into ordered lists and promote short blurbs to headings."""
    content = input_file.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, "html.parser")

    strip_empty_paragraphs(soup)
    listify_numbered_paragraphs(soup)
    promote_short_paragraphs_to_h2(soup, heading_length=heading_length)

    result = BeautifulSoup("<article></article>", "html.parser")
    result.article.append(soup)
    bold_li_prefix_before_colon(result, max_prefix_len=40)
    normalize_strong_spacing(result)
    output_file.write_text(str(result), encoding="utf-8")
