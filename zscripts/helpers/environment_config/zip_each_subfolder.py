import os
import zipfile

from helpers.utilities.paths import org_path

# set the path to the parent folder
parent_folder = str(org_path("Completed_Image_Ratios"))

# loop through each subfolder in the parent folder
for foldername in os.listdir(parent_folder):
    folder_path = os.path.join(parent_folder, foldername)

    # check if the current item in the parent folder is a folder
    if os.path.isdir(folder_path):
        # check if a zip file with the same name as the folder already exists
        zip_filename = foldername + ".zip"
        zip_path = os.path.join(parent_folder, zip_filename)
        if os.path.exists(zip_path):
            print(f"{zip_path} already exists. Skipping {foldername}.")
            continue

        # create a zip file with the same name as the folder
        zip_file = zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED)

        # loop through each file in the folder and add it to the zip file, excluding any zip files
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path) and not file_path.endswith(".zip"):
                zip_file.write(file_path, filename)

        # close the zip file
        zip_file.close()
