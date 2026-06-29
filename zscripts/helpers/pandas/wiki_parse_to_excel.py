import os
from typing import List, Optional, Tuple

from helpers.utilities.paths import org_path

import pandas as pd


def is_valid_line(line: str) -> bool:
    """Return True if the line appears to contain a name – description pair."""
    return ")" in line and " – " in line


def parse_line(line: str) -> Optional[Tuple[str, str]]:
    """Parse a single line into (name, description) if possible."""
    try:
        name, description = line.split(" – ", 1)
        return name.strip(), description.strip()
    except Exception as e:
        print(f"Error parsing line: {line} | Error: {e}")
        return None


def process_files(directory: str) -> List[Tuple[str, str]]:
    parsed_data: List[Tuple[str, str]] = []

    for filename in os.listdir(directory):
        full_path = os.path.join(directory, filename)
        if filename.endswith(".txt"):
            try:
                with open(full_path, "r", encoding="utf-8") as file:
                    print(f"Processing {filename}...")
                    for line in file:
                        if is_valid_line(line):
                            result = parse_line(line)
                            if result:
                                parsed_data.append(result)
            except Exception as e:
                print(f"Error processing {filename}: {e}")

    return parsed_data


directory = str(org_path("Memory", "Python_Parse", "text_docs"))
parsed_lines = process_files(directory)

# Create a DataFrame from the parsed data
df = pd.DataFrame(parsed_lines, columns=["Name", "Description"])

# Write the DataFrame to an Excel file in the script's main directory
excel_path = os.path.join(os.getcwd(), "mythological_creatures.xlsx")
df.to_excel(excel_path, index=False)

print(f"Data written to {excel_path}")
