from PIL import Image


def add_book_file(input_path: str, output_path: str, quality: int) -> None:
    # Open the image and get its current DPI
    img = Image.open(input_path)
    try:
        dpi = img.info["dpi"]
    except KeyError:
        dpi = (300, 300)  # Assume a DPI of 300 if not present

    # Check if the image is horizontal and adjust the dimensions accordingly
    if img.size[0] > img.size[1]:
        # For horizontal images, use a size of 12.125x9 inches
        width = int(12.125 * dpi[0])
        height = int(9 * dpi[1])
    else:
        # For vertical images, use a size of 6.075x9 inches
        width = int(6.075 * dpi[0])
        height = int(9 * dpi[1])
    size = (width, height)

    # Resize the image and save it to the output directory with the same file name
    resized_img = img.resize(size, resample=Image.LANCZOS)
    resized_img.save(output_path, dpi=dpi, quality=quality)
