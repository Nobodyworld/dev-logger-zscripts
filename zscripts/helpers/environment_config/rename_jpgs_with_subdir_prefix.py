import os

from helpers.utilities.paths import org_path

# Set input directory
input_dir = str(org_path("projects", "masky", "input"))

# Loop over all subdirectories in the input directory
for subdir in os.listdir(input_dir):
    subdir_path = os.path.join(input_dir, subdir)
    if os.path.isdir(subdir_path):
        # Loop over all files in the subdirectory
        file_count = 1
        for filename in os.listdir(subdir_path):
            # Rename file with format <subdirectory>_<number>_after.jpg
            if filename.endswith(".jpg"):
                new_filename = f"{subdir}_{file_count}_after.jpg"
                os.rename(os.path.join(subdir_path, filename), os.path.join(subdir_path, new_filename))
                file_count += 1
                print(f"Renamed {filename} to {new_filename}")
