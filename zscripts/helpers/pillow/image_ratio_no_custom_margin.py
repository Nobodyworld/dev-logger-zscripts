import argparse
from pathlib import Path
from typing import Dict, Tuple

from PIL import Image

DPI = (300, 300)
SIZE_CONFIG: Dict[str, Tuple[Tuple[int, int], float]] = {
    "11x14": ((3300, 4200), 0.7),
    "4x5": ((4800, 6000), 0.7),
    "3x4": ((5400, 7200), 0.75),
    "2x3": ((6000, 9000), 0.75),
    "International": ((5906, 8268), 0.75),
}


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _add_vertical_margins(image: Image.Image, margin_pixels: int) -> Image.Image:
    canvas = Image.new("RGB", (image.width, image.height + 2 * margin_pixels), (255, 255, 255))
    canvas.paste(image, (0, margin_pixels))
    return canvas


def process_folder(source_dir: Path, destination_root: Path) -> None:
    """Resize PNGs, adding configurable top/bottom margins prior to resizing."""
    if not source_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {source_dir}")

    for png_path in sorted(source_dir.glob("*.png")):
        try:
            img = Image.open(png_path)
        except OSError as exc:
            print(f"Skipping {png_path.name}: {exc}")
            continue

        filename = png_path.stem
        output_dir = destination_root / filename
        _ensure_directory(output_dir)

        for label, (dimensions, margin_inches) in SIZE_CONFIG.items():
            margin_pixels = int(margin_inches * DPI[0])
            resized = (
                _add_vertical_margins(img, margin_pixels).resize(dimensions)
                if margin_pixels
                else img.resize(dimensions)
            )
            # TODO - add global path function
            output_file = output_dir / f"{filename}_{label}.jpeg"
            try:
                resized.save(output_file, format="JPEG", quality=95, dpi=DPI)
            except OSError as exc:
                print(f"Failed to save {output_file.name}: {exc}")

        img.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resize PNGs into multiple aspect ratios with custom margins."
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing source PNG files.")
    parser.add_argument("output_dir", type=Path, help="Destination directory for resized assets.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input_dir.expanduser().resolve()
    destination = args.output_dir.expanduser().resolve()
    _ensure_directory(destination)
    process_folder(source, destination)


if __name__ == "__main__":
    main()
