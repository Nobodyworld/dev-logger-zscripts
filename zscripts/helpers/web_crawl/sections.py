from pathlib import Path

from bs4 import BeautifulSoup

from .html_ops import section_by_h2

__all__ = ["split_sections"]


def split_sections(input_file: Path, output_file: Path) -> None:
    """Wrap blocks following each H2 in a <section> element."""
    soup = BeautifulSoup(input_file.read_text(encoding="utf-8"), "html.parser")
    section_by_h2(soup)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(soup.prettify(), encoding="utf-8")
