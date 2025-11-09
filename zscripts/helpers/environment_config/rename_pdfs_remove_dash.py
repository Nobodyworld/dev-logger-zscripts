import os

# Get the current directory of the script
directory = os.path.dirname(os.path.realpath(__file__))
print(f"Directory: {directory}")

# Loop through all files in the directory
for filename in os.listdir(directory):
    # Check if the file is a PDF
    if filename.endswith(".pdf"):
        # Check if "test clean" is in the filename
        if " - " in filename:
            # Remove "test clean" from the filename
            new_filename = filename.replace(" - ", "")
            print(f"Renaming {filename} to {new_filename}")
            try:
                # Rename the file
                os.rename(os.path.join(directory, filename), os.path.join(directory, new_filename))
            except Exception as e:
                print(f"Error renaming {filename}: {e}")
        else:
            print(f"No changes needed for {filename}")
