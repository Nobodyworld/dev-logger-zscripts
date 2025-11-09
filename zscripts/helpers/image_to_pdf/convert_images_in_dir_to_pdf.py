import os

import img2pdf

# Get the current working directory
dir_path = os.getcwd()

# Loop through all JPEG files in the directory, convert them to PDF, and save them
for file_name in os.listdir(dir_path):
    if file_name.endswith(".jpeg") or file_name.endswith(".jpg"):
        # Open the image file and convert it to PDF
        jpeg_path = os.path.join(dir_path, file_name)
        pdf_path = os.path.splitext(jpeg_path)[0] + ".pdf"
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(jpeg_path))

# Print a message to indicate that the conversion is complete
print("Conversion complete.")
