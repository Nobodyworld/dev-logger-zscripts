import os

from helpers.pillow.add_watermark import add_watermark
from helpers.utilities.paths import org_path
from PIL import Image

# Define the watermark text, font, and color
font_size = 30
text = "Aureate Vintage"
font_path = "arial.ttf"
font_color = (255, 255, 255, 128)  # RGBA value (white with 50% opacity)
logo_path = "logo.png"

# Set the input and output directories
input_dir = str(org_path("Revenue Streams", "Etsy Shops", "Completed_Image_Ratios"))
output_dir = str(org_path("Revenue Streams", "Etsy Shops", "Completed_Image_Ratios"))

# Loop through all the subdirectories in the input directory
for root, _dirs, files in os.walk(input_dir):
    for file in files:
        if "- Thumbnail -" in file:
            try:
                # Open the image
                img = Image.open(os.path.join(root, file))

                # Calculate the desired size with a 372 pixel white margin on both sides
                original_width, original_height = img.size
                desired_width = 2000
                desired_height = original_height
                margin_size = (desired_width - original_width) // 2
                new_size = (desired_width, desired_height)

                # Add the margins to the image and save it
                new_img = Image.new("RGB", new_size, (255, 255, 255))
                new_img.paste(img, (margin_size, 0))
                output_file = os.path.splitext(file)[0] + "W.jpg"
                output_path = os.path.join(
                    output_dir, root.split(input_dir)[1].lstrip("\\"), output_file
                )
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                new_img.save(output_path, quality=90)

                print(f"Resized {file} and saved as {output_file}")

                # Convert the image to RGBA mode
                img = img.convert("RGBA")

                # Add the watermark to the image
                watermark_path = os.path.join(
                    output_dir,
                    root.split(input_dir)[1].lstrip("\\"),
                    os.path.splitext(file)[0] + "W.jpg",
                )
                add_watermark(
                    output_path,
                    watermark_path,
                    text=text,
                    font_size=font_size,
                    font_path=font_path,
                    font_color=font_color,
                    logo_path=logo_path,
                )
                print(f"Watermarked {output_file}")

                # Remove the old thumbnail file
                os.remove(os.path.join(root, file))
                print(f"Removed {file}")

            except Exception as e:
                print(f"An error occurred while processing file {file}: {e}")
