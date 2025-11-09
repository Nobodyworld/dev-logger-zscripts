from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


def add_watermark(
    input_path: str,
    output_path: str,
    text: str = "Aureate Vintage",
    font_size: int = 30,
    font_path: str = "arial.ttf",
    font_color: Tuple[int, int, int, int] = (255, 255, 255, 128),
    logo_path: Optional[str] = None,
) -> None:
    # Define the watermark font, fallback to default if truetype unavailable
    try:
        font = ImageFont.truetype(font_path, font_size * 2)
    except Exception:
        font = ImageFont.load_default()

    # Load the logo image if specified
    logo = None
    if logo_path is not None:
        logo = Image.open(logo_path)

    try:
        # Open the image and convert it to RGBA mode
        img = Image.open(input_path).convert("RGBA")

        # Create a transparent image with the same size as the original image
        watermark = Image.new("RGBA", img.size, (0, 0, 0, 0))

        # Add the watermark to the transparent image
        draw = ImageDraw.Draw(watermark)
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        draw = ImageDraw.Draw(watermark)
        draw.text(
            ((img.width - text_width) / 2, (img.height - text_height) / 2),
            text,
            font=font,
            fill=font_color,
        )

        # Add the logo to the watermark image
        if logo is not None:
            logo_width, logo_height = int(img.width * 0.2), int(img.height * 0.2)
            logo = logo.resize((logo_width, logo_height), resample=Image.LANCZOS)
            watermark.paste(logo, (img.width - logo_width, img.height - logo_height), logo)

        # Composite the original image with the watermark image
        watermarked_img = Image.alpha_composite(img, watermark)

        # Save the watermarked image in PNG format
        watermarked_img.save(output_path, format="PNG")

    except IOError as e:
        print(f"Could not process image file {input_path}: {e}")
