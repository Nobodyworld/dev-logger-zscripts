from pathlib import Path

from PIL import Image

from .config import DEFAULT_PROFILES, DPI

__all__ = ["process_folder"]


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _add_vertical_margins(image: Image.Image, margin_pixels: int) -> Image.Image:
    padded = Image.new("RGB", (image.width, image.height + 2 * margin_pixels), (255, 255, 255))
    padded.paste(image, (0, margin_pixels))
    return padded


def process_folder(source_dir: Path, destination_root: Path) -> None:
    """Resize every PNG in `source_dir` into multiple aspect ratios.

    Uses per-profile margin settings from helpers.pillow.config.DEFAULT_PROFILES.
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {source_dir}")

    for png_path in sorted(source_dir.glob("*.png")):
        with Image.open(png_path) as img:
            filename = png_path.stem
            output_dir = destination_root / filename
            _ensure_directory(output_dir)

            for profile in DEFAULT_PROFILES:
                resized = (
                    _add_vertical_margins(img, int(profile.margin_inches * DPI[0])).resize(profile.size)
                    if profile.margin_inches
                    else img.resize(profile.size)
                )
                # TODO - add global path function
                output_file = output_dir / f"{filename}_{profile.label}{png_path.suffix}"
                resized.save(output_file, dpi=DPI)
