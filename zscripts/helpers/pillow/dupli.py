import argparse
import re
import shutil
from pathlib import Path

from PIL import Image


def find_duplicates(dir_path: Path):
    # A regex pattern to identify images that end in " (#)"
    # TODO - add global path function
    pattern = re.compile(r"^(.*) \(\d\)$")
    files = [entry.name for entry in dir_path.iterdir()]

    duplicates = {}

    for file in files:
        match = pattern.match(
            file.rsplit(".", 1)[0]
        )  # Splitting filename and extension and matching filename.

        if match:
            original_name = match.group(1)  # Extract the name before the " (#)"
            # Construct the original filename with its extension (wrapped for line length)
            ext = file.rsplit(".", 1)[1]
            original_file = f"{original_name}.{ext}"

            if original_file in files:
                # Comparing sizes as a quick first check
                if (dir_path / file).stat().st_size == (dir_path / original_file).stat().st_size:
                    duplicates[file] = original_file

    return duplicates


def are_images_identical(img1_path: Path, img2_path: Path):
    try:
        # Open the images and get their size and aspect ratio
        with Image.open(img1_path) as img1, Image.open(img2_path) as img2:
            if img1.size != img2.size:
                return False
            if img1.size[0] / img1.size[1] != img2.size[0] / img2.size[1]:
                return False

            # You can add more checks if you want, such as pixel-by-pixel comparison.
            # For now, only size and aspect ratio are being checked.

        return True
    except Exception:
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find duplicate JPGs ending with '(#)' suffix.")
    parser.add_argument("directory", type=Path, help="Directory containing images.")
    parser.add_argument(
        "--review-subdir",
        default="review",
        help="Subdirectory to move duplicates into (default: review)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dir_path = args.directory.expanduser().resolve()
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    review_path = dir_path / args.review_subdir

    review_path.mkdir(exist_ok=True)

    duplicates = find_duplicates(dir_path)

    for duplicate, original in duplicates.items():
        if are_images_identical(dir_path / duplicate, dir_path / original):
            shutil.move(dir_path / duplicate, review_path)


if __name__ == "__main__":
    main()
