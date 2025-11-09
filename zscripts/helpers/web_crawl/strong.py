from pathlib import Path

from bs4 import BeautifulSoup

from .html_ops import bold_li_prefix_before_colon

__all__ = ["apply_strong_prefixes"]


def apply_strong_prefixes(input_file: Path, output_file: Path, max_prefix_len: int = 40) -> None:
    """Apply <strong> to the short prefix before ':' within list items."""
    soup = BeautifulSoup(input_file.read_text(encoding="utf8"), "html.parser")
    bold_li_prefix_before_colon(soup, max_prefix_len=max_prefix_len)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(soup.prettify(), encoding="utf8")
