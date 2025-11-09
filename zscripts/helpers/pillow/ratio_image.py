import os
import shutil

from PIL import Image

from helpers.utilities.paths import org_path

# Define the new aspect ratios and their recommended resolutions
aspect_ratios = [
    ("3x4", (7200, 9600)),
    ("2x3", (7200, 10800)),
    ("11x14", (6600, 8400)),
    ("International", (7020, 9933)),
    ("Letter", (2550, 3300)),
    ("Ledger", (3300, 5100)),
    ("Thumbnail", (2700, 2025)),
]

# Get the directory containing the files via org_path
edit_these_folder = str(org_path("project_user", "projects", "resize", "input"))
processed_folder = str(org_path("project_user", "projects", "resize", "processed"))
product_name = "Tests"

# Create a folder to store the image ratios
os.makedirs(processed_folder, exist_ok=True)

# Loop through each file
for file in os.listdir(edit_these_folder):
    if file.lower().endswith((".jpg", ".jpeg")):
        print(f"Processing file: {file}")
        try:
            # Move the original image to the processed folder
            numerical_tag = os.path.splitext(file)[0].split("_")[-1]
            if not numerical_tag.isdigit():
                continue
            file_folder = os.path.join(processed_folder, f"{product_name} - {numerical_tag}")
            os.makedirs(file_folder, exist_ok=True)
            shutil.move(os.path.join(edit_these_folder, file), os.path.join(file_folder, file))
            print(f"Moved original image to: {os.path.join(file_folder, file)}")

            # Open the image
            img = Image.open(os.path.join(file_folder, file))

            # Loop through each aspect ratio and resize the image accordingly
            for size, (width, height) in aspect_ratios:
                print(f"Resizing {size} image...")
                if size == "Thumbnail":
                    # Determine the aspect ratio of the original image
                    orig_width, orig_height = img.size
                    orig_ratio = orig_width / orig_height
                    # Resize the image using the same aspect ratio as the original image
                    new_width = int(height * orig_ratio)
                    img_resized = img.resize((new_width, height), resample=Image.LANCZOS)
                else:
                    # Resize the image to the recommended resolution for the aspect ratio
                    img_resized = img.resize((width, height), resample=Image.LANCZOS)

                # Save the resized image in the new folder
                new_filename = f"{product_name} - {size} - {file}"
                print(f"Saving resized image to: {os.path.join(file_folder, new_filename)}")
                try:
                    # Set DPI to 300 and save the image
                    dpi = (300, 300)
                    img_resized.save(
                        os.path.join(file_folder, new_filename),
                        format="JPEG",
                        quality=100,
                        dpi=dpi,
                    )
                    print(f"Saved {new_filename}")
                except IOError as e:
                    print(f"Could not save image file {new_filename}: {e}")
                except Exception as e:
                    print(f"An error occurred while saving image {new_filename}: {e}")

        except Exception as e:
            print(f"An error occurred while processing file {file}: {e}")
            continue
