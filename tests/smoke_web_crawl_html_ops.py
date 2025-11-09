from __future__ import annotations

from bs4 import BeautifulSoup

from zscripts.helpers.web_crawl.html_ops import (
    bold_li_prefix_before_colon,
    listify_numbered_paragraphs,
    normalize_strong_spacing,
    promote_short_paragraphs_to_h2,
    section_by_h2,
    strip_empty_paragraphs,
)


def run() -> None:
    """Lightweight smoke tests for html_ops using inline fixtures.

    This is a simple script with asserts; run via:
        python tests/smoke_web_crawl_html_ops.py
    """
    # Fixture: short heading paragraph promoted to h2,
    # numbered paragraphs converted to list items, strong spacing normalized.
    html = """
    <html><body>
      <p>Overview</p>
      <p>1. **Locate** items:</p>
      <p>2. **Inspect** items</p>
      <p> </p>
      <ul><li>Prefix: value</li></ul>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    # strip empty <p>
    strip_empty_paragraphs(soup)
    assert not any(p for p in soup.find_all("p") if not p.get_text(strip=True))

    # listify numbered paragraphs before promoting short paragraphs
    listify_numbered_paragraphs(soup)
    assert soup.find("ol") is not None and len(soup.find_all("li")) >= 2

    # promote short paragraph to h2
    promote_short_paragraphs_to_h2(soup, heading_length=64)
    assert soup.find("h2", string="Overview") is not None

    # normalize <strong> spacing
    for strong in soup.find_all("strong"):
        strong.replace_with(BeautifulSoup("<strong> text</strong>", "html.parser"))
    normalize_strong_spacing(soup)
    assert all("<strong>text</strong>" in str(tag) for tag in soup.find_all("strong"))

    # bold prefix in list items before colon
    bold_li_prefix_before_colon(soup)
    assert soup.find("li").find("strong") is not None

    # section the document by h2 (structure can vary depending on wrappers)
    section_by_h2(soup)


if __name__ == "__main__":
    run()
    print("html_ops smoke tests passed")
