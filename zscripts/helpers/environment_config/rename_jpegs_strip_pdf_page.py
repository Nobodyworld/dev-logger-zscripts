import os
from pathlib import Path
from typing import Iterable


def strip_pdf_page_suffix(folder: Path) -> Iterable[tuple[str, str]]:
    """Strip '.pdf_page' from .jpeg filenames inside a folder.

    Yields tuples of (old_name, new_name) for renamed files.
    """
    for filename in os.listdir(folder):
        if filename.lower().endswith(".jpeg") and ".pdf_page" in filename:
            new_filename = filename.replace(".pdf_page", "")
            try:
                os.rename(folder / filename, folder / new_filename)
                yield filename, new_filename
            except Exception as e:
                print(f"Error renaming {filename}: {e}")


if __name__ == "__main__":
    directory = Path(__file__).resolve().parent
    for old, new in strip_pdf_page_suffix(directory):
        print(f"Renamed {old} to {new}")
