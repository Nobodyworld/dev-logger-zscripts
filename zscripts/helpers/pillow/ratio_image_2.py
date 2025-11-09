import os

from PIL import Image, ImageFilter


def resize_images_by_ratio(image_path: str, output_folder: str, filename: str) -> None:
    # Open the image and get the dimensions
    image = Image.open(image_path)
    width, height = image.size

    # Calculate the longest edge
    longest_edge = max(width, height)

    # Calculate the resize ratio
    ratio = 1000 / longest_edge

    # Calculate the new dimensions
    new_width = round(width * ratio)
    new_height = round(height * ratio)

    # Resize the image
    resized_image = image.resize((new_width, new_height))

    # Save the resized image to the output folder
    output_path = os.path.join(output_folder, filename + ".jpg")
    resized_image.save(output_path)


def resize_images_by_aspect_ratio(image_path: str, output_folder: str, filename: str) -> None:
    # Open the image and get the dimensions
    image = Image.open(image_path)
    width, height = image.size

    # Define the new aspect ratios and their recommended resolutions
    aspect_ratios = [
        ("3x4", (7200, 9600)),
        ("2x3", (7200, 10800)),
        ("11x14", (6600, 8400)),
        ("International", (7020, 9933)),
    ]

    # Loop through each aspect ratio and resize the image accordingly
    for size, (width_ratio, height_ratio) in aspect_ratios:
        # Calculate the new dimensions for the aspect ratio based on the longest edge of the image
        longest_edge = max(width, height)
        new_width = (
            round(longest_edge * width_ratio / height_ratio)
            if width_ratio > height_ratio
            else longest_edge
        )
        new_height = (
            round(longest_edge * height_ratio / width_ratio)
            if width_ratio < height_ratio
            else longest_edge
        )

        # Resize the image to the new dimensions
        img_resized = image.resize((new_width, new_height), resample=Image.LANCZOS)
        img_resized = img_resized.filter(ImageFilter.SHARPEN)

        # Create the folder to save the resized images and copy the original file
        file_name = f"{filename}_{size}.jpeg"
        file_folder = os.path.join(output_folder, "ratio_image")
        if not os.path.exists(file_folder):
            os.makedirs(file_folder)

        # Save the resized image in the new folder
        try:
            img_resized.save(os.path.join(file_folder, file_name), format="JPEG", quality=100)
        except IOError as e:
            print(f"Could not save image file {file_name}: {e}")
