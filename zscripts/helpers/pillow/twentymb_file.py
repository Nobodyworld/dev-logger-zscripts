import os

from PIL import Image

from helpers.utilities.paths import org_path


def compress_image(image_path: str, max_file_size: int = 20 * 1024 * 1024) -> None:
    img = Image.open(image_path)
    quality = 90
    file_size = os.path.getsize(image_path)

    # The following loop only modifies the compression quality, not the aspect ratio.
    while file_size > max_file_size and quality > 10:
        img.save(image_path, format="JPEG", quality=quality)
        quality -= 5
        file_size = os.path.getsize(image_path)


def main() -> None:
    target_directory = str(org_path("Revenue Streams", "images_process", "d.ready_to_post"))
    max_file_size = 20 * 1024 * 1024

    for root, _dirs, files in os.walk(target_directory):
        for file in files:
            if file.lower().endswith((".jpg", ".jpeg")):
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)

                if file_size > max_file_size:
                    compress_image(file_path, max_file_size)


if __name__ == "__main__":
    main()
