import argparse
import shutil
from pathlib import Path
from typing import Iterable

PREFERRED_LISTING1 = {"2x3", "3x4", "11x14"}
PREFERRED_LISTING2 = {"International", "Ledger", "Letter"}


def _ensure_subfolders(base: Path) -> tuple[Path, Path]:
    # TODO - add global path function
    listing1 = base / "listing1"
    # TODO - add global path function
    listing2 = base / "listing2"
    listing1.mkdir(exist_ok=True)
    listing2.mkdir(exist_ok=True)
    return listing1, listing2


def _iter_source_images(base: Path) -> Iterable[Path]:
    for entry in base.iterdir():
        if entry.is_file() and entry.suffix.lower() == ".jpg":
            yield entry


def sort_listings(main_dir: Path) -> None:
    """Ensure listing subfolders exist and move JPEGs according to naming patterns."""
    if not main_dir.exists():
        raise FileNotFoundError(f"Listing directory not found: {main_dir}")

    for subfolder in sorted(path for path in main_dir.iterdir() if path.is_dir()):
        listing1, listing2 = _ensure_subfolders(subfolder)

        for file_path in _iter_source_images(subfolder):
            parts = file_path.stem.split("-")
            if len(parts) < 2:
                continue

            identifier = parts[1].strip()
            destination = None
            if identifier in PREFERRED_LISTING1:
                destination = listing1 / file_path.name
            elif identifier in PREFERRED_LISTING2:
                destination = listing2 / file_path.name

            if destination:
                try:
                    shutil.move(str(file_path), destination)
                    print(f"Moved {file_path.name} -> {destination.parent.name}")
                except OSError as exc:
                    print(f"Error moving {file_path.name}: {exc}")

        print(f"{subfolder.name}/listing1: {sorted(p.name for p in listing1.iterdir())}")
        print(f"{subfolder.name}/listing2: {sorted(p.name for p in listing2.iterdir())}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organise listing JPEGs into variant subfolders.")
    parser.add_argument(
        "directory", type=Path, help="Root directory containing per-listing folders."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    main_dir = args.directory.expanduser().resolve()
    sort_listings(main_dir)


if __name__ == "__main__":
    main()
