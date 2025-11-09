import os
import re
import shutil

from helpers.utilities.paths import org_path

main_dir = str(org_path("Revenue Streams", "images_process", "c.completed_image_ratios"))

# Define regular expression patterns to match the identifiers
listing1_pattern = r"\b(2x3|3x4|11x14)\b"
listing2_pattern = r"\b(International|Ledger|Letter)\b"

# Loop through all the subfolders of the main directory
for root, dirs, files in os.walk(main_dir):
    # Only consider subfolders directly under the main directory
    if root == main_dir:
        for subfolder in dirs:
            # Check if the subfolder already contains listing1 and listing2 subfolders
            subfolder_path = os.path.join(root, subfolder)
            listing1_path = os.path.join(subfolder_path, "AureateVintage1")
            listing2_path = os.path.join(subfolder_path, "AureateVintage2")
            if not os.path.exists(listing1_path):
                os.mkdir(listing1_path)
                print(f"Created listing1 folder in {subfolder_path}")
            if not os.path.exists(listing2_path):
                os.mkdir(listing2_path)
                print(f"Created listing2 folder in {subfolder_path}")

            # Loop through the JPG files in the subfolder
            for file_name in [f for f in files if f.endswith(".jpg")]:
                # Check if the file matches the naming convention using regular expressions
                match = re.search(r"(?P<name>.*)-(?P<identifier>.*)\.jpg", file_name)
                if match:
                    name = match.group("name").strip()
                    identifier = match.group("identifier").strip()
                    # Check if the identifier matches one of the patterns
                    if re.search(listing1_pattern, identifier):
                        # Move the file to listing1
                        src_path = os.path.join(subfolder_path, file_name)
                        dst_path = os.path.join(listing1_path, file_name)
                        try:
                            shutil.move(src_path, dst_path)
                            print(f"Moved {file_name} to {listing1_path}")
                        except Exception as e:
                            print(f"Error moving {file_name}: {e}")
                    elif re.search(listing2_pattern, identifier):
                        # Move the file to listing2
                        src_path = os.path.join(subfolder_path, file_name)
                        dst_path = os.path.join(listing2_path, file_name)
                        try:
                            shutil.move(src_path, dst_path)
                            print(f"Moved {file_name} to {listing2_path}")
                        except Exception as e:
                            print(f"Error moving {file_name}: {e}")

            # Print the list of files in the listing folders
            listing1_files = os.listdir(listing1_path)
            listing2_files = os.listdir(listing2_path)
            print(f"Listing 1 files in {listing1_path}: {listing1_files}")
            print(f"Listing 2 files in {listing2_path}: {listing2_files}")
