import os

from PIL import Image

from helpers.utilities.paths import org_path

# Use org_path for the input directory
input_dir = str(org_path("projects", "masky", "input"))

for filename in os.listdir(input_dir):
    if filename.endswith("_before.jpg"):
        # Get the matching after image filename
        after_filename = filename.replace("_before.jpg", "_after.jpg")
        after_filepath = os.path.join(input_dir, after_filename)

        # Open the before and after images
        before_filepath = os.path.join(input_dir, filename)
        before_img = Image.open(before_filepath)
        after_img = Image.open(after_filepath)

        # Get the resolution and dpi of the after image
        after_resolution = after_img.size
        after_dpi = after_img.info.get("dpi")

        # Resize the before image to match the resolution of the after image
        before_img = before_img.resize(after_resolution)

        # Set the dpi of the before image to match the dpi of the after image
        if after_dpi:
            before_img.info["dpi"] = after_dpi

        # Save the modified before image with the same filename
        before_img.save(before_filepath)

        print(f"Resized and set DPI for {filename}")
