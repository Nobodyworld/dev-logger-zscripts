import pandas as pd
from helpers.utilities.paths import org_path

# Define the file path and sheet name
file_path = str(org_path("scripts", "this_one.xlsx"))
sheet_name = "Sheet1"

# Read the Excel file
df = pd.read_excel(file_path, sheet_name=sheet_name)

# Initialize an empty DataFrame to store the results
result = pd.DataFrame()

# Go through each column
for col in df.columns:
    # Drop the blank cells and reset the index
    column_data = df[col].dropna().reset_index(drop=True)

    # Add the processed column to the result DataFrame
    result = pd.concat([result, column_data], axis=1)

# Write the result DataFrame into a new Excel file via org_path
result.to_excel(str(org_path("scripts", "output.xlsx")), index=False)
