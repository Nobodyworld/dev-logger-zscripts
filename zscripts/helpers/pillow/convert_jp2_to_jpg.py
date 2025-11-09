import os
from typing import Optional

from PIL import Image


def convert_jp2_to_jpg(jp2_path: str, jpg_path: Optional[str] = None) -> None:
    # Open the image
    with Image.open(jp2_path) as img:
        # Save it to the desired format
        img.save(jpg_path or jp2_path.replace(".jp2", ".jpg"), "JPEG")


if __name__ == "__main__":
    source_directory = input("Enter the directory containing JP2 images: ")

    # Iterate through each file in the directory
    for filename in os.listdir(source_directory):
        if filename.endswith(".jp2"):
            full_path = os.path.join(source_directory, filename)
            convert_jp2_to_jpg(full_path)
            print(f"Converted {filename} to JPG format.")

    print("All JP2 images have been converted to JPG!")
