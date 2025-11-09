import argparse
from pathlib import Path
from typing import Dict, Tuple

from PIL import Image

DPI = (300, 300)
SIZE_CONFIG: Dict[str, Tuple[Tuple[int, int], float]] = {
    "11x14": ((3300, 4200), 0.7),
    "4x5": ((4800, 6000), 0.7),
    "3x4": ((5400, 7200), 0.75),
    "2x3": ((6000, 9000), 1.0),
    "International": ((5906, 8268), 0.75),
}
HORIZONTAL_MARGIN_INCHES = 0.2


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def dominant_tint(image_path: Path) -> Tuple[int, int, int]:
    """Estimate a soft background colour based on the image's most common grayscale value."""
    with Image.open(image_path).convert("L") as grayscale:
        histogram = grayscale.histogram()
        max_index = max(range(len(histogram)), key=histogram.__getitem__)
        blend = (255 + max_index) // 2
        return blend, blend, blend


def _add_margins(
    image: Image.Image, vertical_margin: int, horizontal_margin: int, colour: Tuple[int, int, int]
) -> Image.Image:
    canvas = Image.new(
        "RGB",
        (image.width + 2 * horizontal_margin, image.height + 2 * vertical_margin),
        colour,
    )
    canvas.paste(image, (horizontal_margin, vertical_margin))
    return canvas


def process_folder(source_dir: Path, destination_root: Path) -> None:
    """Resize PNG files applying blended margins derived from the dominant image tint."""
    if not source_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {source_dir}")

    horizontal_margin = int(HORIZONTAL_MARGIN_INCHES * DPI[0])

    for png_path in sorted(source_dir.glob("*.png")):
        try:
            img = Image.open(png_path)
        except OSError as exc:
            print(f"Skipping {png_path.name}: {exc}")
            continue

        filename = png_path.stem
        output_dir = destination_root / filename
        _ensure_directory(output_dir)
        base_colour = dominant_tint(png_path)

        for label, (dimensions, vertical_inches) in SIZE_CONFIG.items():
            vertical_margin = int(vertical_inches * DPI[0])
            if vertical_margin:
                working = _add_margins(img, vertical_margin, horizontal_margin, base_colour)
            else:
                working = img
            resized = working.resize(dimensions)
            # TODO - add global path function
            output_file = output_dir / f"{filename}_{label}.jpeg"
            try:
                resized.save(output_file, format="JPEG", quality=95, dpi=DPI)
            except OSError as exc:
                print(f"Failed to save {output_file.name}: {exc}")

        img.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resize PNGs while blending margins based on dominant tones."
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing PNG files to process.")
    parser.add_argument("output_dir", type=Path, help="Destination directory for generated assets.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input_dir.expanduser().resolve()
    destination = args.output_dir.expanduser().resolve()
    _ensure_directory(destination)
    process_folder(source, destination)


if __name__ == "__main__":
    main()
