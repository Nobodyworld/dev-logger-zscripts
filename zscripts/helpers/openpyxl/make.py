import os

from helpers.utilities.paths import org_path

from openpyxl import Workbook

# Directory path
directory_path = str(org_path("data", "data_gen", "aes"))

# Create a new workbook and get the active worksheet
wb = Workbook()
ws = wb.active

# Iterate through each file in the directory
for idx, filename in enumerate(os.listdir(directory_path), start=1):
    # Construct the full file path
    file_path = os.path.join(directory_path, filename)

    # Check if it's a text file
    if file_path.endswith(".txt"):
        # Read the file and store its content
        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            content = file.read()

        # Write the content to the Excel cell (idx, 1) => (row, column)
        ws.cell(row=idx, column=1).value = content

# Save the workbook to an Excel file
output_file = os.path.join(directory_path, "combined_data.xlsx")
wb.save(output_file)

print(f"Data saved to {output_file}")
