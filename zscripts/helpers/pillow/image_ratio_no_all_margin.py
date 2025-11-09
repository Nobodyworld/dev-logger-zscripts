import argparse
from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image

DPI = (300, 300)
SIZES: Iterable[Tuple[str, Tuple[int, int]]] = (
    ("11x14", (3300, 4200)),
    ("4x5", (4800, 6000)),
    ("3x4", (5400, 7200)),
    ("2x3", (6000, 9000)),
    ("International", (5906, 8268)),
)
MARGIN_INCHES = 0.2


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _add_vertical_margins(image: Image.Image, margin_pixels: int) -> Image.Image:
    canvas = Image.new("RGB", (image.width, image.height + 2 * margin_pixels), (255, 255, 255))
    canvas.paste(image, (0, margin_pixels))
    return canvas


def process_folder(
    source_dir: Path, destination_root: Path, margin_inches: float = MARGIN_INCHES
) -> None:
    """Resize PNGs, adding a uniform vertical margin before scaling."""
    if not source_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {source_dir}")

    margin_pixels = int(margin_inches * DPI[0])

    for png_path in sorted(source_dir.glob("*.png")):
        try:
            img = Image.open(png_path)
        except OSError as exc:
            print(f"Skipping {png_path.name}: {exc}")
            continue

        filename = png_path.stem
        output_dir = destination_root / filename
        _ensure_directory(output_dir)

        for label, dimensions in SIZES:
            working = _add_vertical_margins(img, margin_pixels) if margin_pixels else img
            resized = working.resize(dimensions)
            # TODO - add global path function
            output_file = output_dir / f"{filename}_{label}.jpeg"
            try:
                resized.save(output_file, format="JPEG", quality=95, dpi=DPI)
            except OSError as exc:
                print(f"Failed to save {output_file.name}: {exc}")

        img.close()


def parse_args() -> argparse.Namespace:
    # TODO - add global path function
    parser = argparse.ArgumentParser(description="Resize PNGs with consistent top/bottom margins.")
    parser.add_argument("input_dir", type=Path, help="Directory containing PNG files.")
    parser.add_argument("output_dir", type=Path, help="Destination directory for resized images.")
    parser.add_argument(
        "--margin",
        type=float,
        default=MARGIN_INCHES,
        help="Vertical margin (in inches) to add before resizing (default: 0.2).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input_dir.expanduser().resolve()
    destination = args.output_dir.expanduser().resolve()
    _ensure_directory(destination)
    process_folder(source, destination, margin_inches=args.margin)


if __name__ == "__main__":
    main()
