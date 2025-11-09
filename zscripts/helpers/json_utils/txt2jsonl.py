import json
import re
from typing import Dict

from helpers.utilities.paths import org_path


def extract_to_jsonl(input_file_path: str, output_file_path: str) -> None:
    """Extract categories from a text file into JSONL.

    Focuses on Power Platform components and writes a JSON object per line.
    """
    # Define categories and their respective patterns for extraction
    categories = {
        "Power Apps": r"Power Apps:(.*?)(?=\n\S+:|$)",
        "Power Flows": r"Power Flows:(.*?)(?=\n\S+:|$)",
        "Tables": r"Tables:(.*?)(?=\n\S+:|$)",
        "Lists": r"Lists:(.*?)(?=\n\S+:|$)",
        "GPTs": r"GPTs:(.*?)(?=\n\S+:|$)",
        "Attributes": r"Attributes:(.*?)(?=\n\S+:|$)",
        "Skills": r"Skills:(.*?)(?=\n\S+:|$)",
        # Add more categories as needed
    }

    # Read the entire content of the input file
    with open(input_file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # Extract and categorize content
    categorized_data: Dict[str, str] = {}
    for category, pattern in categories.items():
        match = re.search(pattern, content, re.DOTALL)
        if match:
            categorized_data[category] = match.group(1).strip()

    # Write the categorized content to a JSONL file
    with open(output_file_path, "w", encoding="utf-8") as jsonl_file:
        for category, data in categorized_data.items():
            json.dump({category: data}, jsonl_file)
            jsonl_file.write("\n")


# Define the input and output file paths
input_file_path = str(org_path("Shared Documents - GPTs", "Main.txt"))
output_file_path = str(org_path("Shared Documents - GPTs", "categorized_content.jsonl"))

# Call the function to perform the extraction and categorization
extract_to_jsonl(input_file_path, output_file_path)

print("Extraction and categorization complete. File saved at:", output_file_path)
