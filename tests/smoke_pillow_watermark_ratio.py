from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from zscripts.helpers.pillow.add_watermark import add_watermark
from zscripts.helpers.pillow.ratio_image_2 import (
    resize_images_by_aspect_ratio,
    resize_images_by_ratio,
)


def run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_img = tmp_path / "input.png"
        logo_img = tmp_path / "logo.png"
        out_watermarked = tmp_path / "watermarked.png"

        # Create a simple input image and a small logo
        Image.new("RGB", (200, 100), color=(120, 180, 200)).save(input_img)
        Image.new("RGBA", (40, 40), color=(255, 0, 0, 128)).save(logo_img)

        # Watermark (fallback to default font if truetype missing)
        add_watermark(
            str(input_img),
            str(out_watermarked),
            text="Test",
            font_size=12,
            font_path="arial.ttf",
            logo_path=str(logo_img),
        )
        assert out_watermarked.exists()

        # Ratio resize
        ratio_out_dir = tmp_path / "ratio"
        ratio_out_dir.mkdir(exist_ok=True)
        resize_images_by_ratio(str(input_img), str(ratio_out_dir), "sample")
        assert (ratio_out_dir / "sample.jpg").exists()

        # Aspect ratio variations
        resize_images_by_aspect_ratio(str(input_img), str(ratio_out_dir), "sample")
        aspect_dir = ratio_out_dir / "ratio_image"
        assert aspect_dir.exists()
        files = list(aspect_dir.glob("sample_*.jpeg"))
        assert files, "Expected at least one aspect-resized output"


if __name__ == "__main__":
    run()
    print("pillow watermark/ratio smoke test passed")
