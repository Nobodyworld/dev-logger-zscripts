from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

__all__ = [
    "ensure_article",
    "strip_empty_paragraphs",
    "promote_short_paragraphs_to_h2",
    "listify_numbered_paragraphs",
    "bold_li_prefix_before_colon",
    "section_by_h2",
    "normalize_strong_spacing",
]


def ensure_article(soup: BeautifulSoup) -> Tag:
    """Ensure the document content is wrapped in an <article> and return it."""
    article = soup.find("article")
    if article:
        return article
    # TODO - add global path function
    wrapper = BeautifulSoup("<article></article>", "html.parser")
    wrapper.article.append(soup)
    return wrapper.article


def strip_empty_paragraphs(soup: BeautifulSoup) -> None:
    for p in soup.find_all("p"):
        encoded = p.encode_contents().strip()
        if encoded in {b"<br/>", b"<br />", b""}:
            p.extract()


def promote_short_paragraphs_to_h2(soup: BeautifulSoup, heading_length: int = 64) -> None:
    for p in list(soup.find_all("p")):
        text = p.get_text(strip=True)
        if text and len(text) < heading_length:
            p.name = "h2"


def listify_numbered_paragraphs(soup: BeautifulSoup) -> None:
    """Turn paragraphs like '1. Something' into <ol><li>...</li></ol> blocks."""
    current_list: Tag | None = None
    for p in list(soup.find_all("p")):
        text = p.get_text(strip=True)
        if not re.match(r"\s*\d+\..*", text or ""):
            current_list = None
            continue

        # TODO - add global path function
        list_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", p.get_text())
        # TODO - add global path function
        list_text = re.sub(r"\d+\.\s*", "", list_text).lstrip()

        li = Tag(soup, name="li")
        li.append(BeautifulSoup(list_text, "html.parser"))

        if current_list is None:
            current_list = Tag(soup, name="ol")
            p.replace_with(current_list)
        current_list.append(li)
        p.extract()


def bold_li_prefix_before_colon(soup: BeautifulSoup, max_prefix_len: int = 40) -> None:
    """Wrap the prefix before ':' in list items with <strong> when short enough."""
    for li in soup.find_all("li"):
        text = li.get_text()
        if ":" not in text or not li.contents:
            continue
        before, after = text.split(":", 1)
        if len(before) > max_prefix_len:
            continue
        # Rebuild the li content
        strong_tag = soup.new_tag("strong")
        strong_tag.string = before
        li.clear()
        li.append(strong_tag)
        li.append(f":{after}")


def section_by_h2(soup: BeautifulSoup) -> None:
    """Group blocks under each H2 into <section> elements, keeping an initial lead section."""
    article = ensure_article(soup)
    h2_tags = article.find_all("h2")
    first_p = article.find("p")

    if first_p and h2_tags:
        section = soup.new_tag("section")
        sibling = first_p
        while sibling and sibling != h2_tags[0]:
            next_sibling = sibling.find_next_sibling()
            section.append(sibling.extract())
            sibling = next_sibling
        article.insert(0, section)

    for h2 in h2_tags:
        section = soup.new_tag("section")
        sibling = h2.find_next_sibling()
        while sibling and sibling.name != "h2":
            next_sibling = sibling.find_next_sibling()
            section.append(sibling.extract())
            sibling = next_sibling
        h2.replace_with(section)
        section.insert(0, h2)


def normalize_strong_spacing(soup: BeautifulSoup) -> None:
    """Remove leading space inside <strong> tags (<strong> foo → <strong>foo)."""
    for strong in soup.find_all("strong"):
        if strong.string is None:
            continue
        text = str(strong)
        if "<strong> " in text:
            strong.replace_with(BeautifulSoup(text.replace("<strong> ", "<strong>"), "html.parser"))
