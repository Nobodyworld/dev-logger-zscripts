import io
import os
import re
from typing import Tuple

import openpyxl
from helpers.utilities.paths import org_path
from PIL import Image, ImageOps


def sanitize_filename(name: str) -> str:
    """Sanitize the filename to ensure it is valid for saving."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def extract_and_save_images_from_excel(
    excel_file_path: str, output_directory: str, target_size: Tuple[int, int] = (200, 200)
) -> None:
    # Load the workbook and active sheet
    workbook = openpyxl.load_workbook(excel_file_path, data_only=True)
    sheet = workbook.active

    # Extract all images
    images = sheet._images

    # Extract all hyperlinks
    hyperlinks = []
    for row in sheet.iter_rows():
        for cell in row:
            if cell.hyperlink and cell.hyperlink.target:
                hyperlinks.append(cell.hyperlink.target)

    # Ensure output directory has a trailing separator
    if not output_directory.endswith(os.sep):
        output_directory = output_directory + os.sep

    # Save images with sequential names and map them to hyperlinks
    mapping = {}
    for i, img in enumerate(images, start=1):
        image_name = f"Image_{i}.png"
        mapping[image_name] = hyperlinks[i - 1] if i <= len(hyperlinks) else "No hyperlink"

        # Extract and save the image
        image_data = img._data()
        image = Image.open(io.BytesIO(image_data))
        image = ImageOps.fit(image, target_size, Image.Resampling.LANCZOS)  # Resize the image
        image.save(output_directory + sanitize_filename(image_name))

    # Optionally, save the mapping to a file
    with open(output_directory + "image_hyperlink_mapping.txt", "w", encoding="utf-8") as file:
        for image_name, hyperlink in mapping.items():
            file.write(f"{image_name}: {hyperlink}\n")


# Usage

excel_file_path = str(org_path("Shared Documents - GPTs", "pasted_gpt_thumbnail_and_link.xlsx"))
output_directory = str(org_path("Shared Documents - GPTs", "test"))

extract_and_save_images_from_excel(excel_file_path, output_directory)
