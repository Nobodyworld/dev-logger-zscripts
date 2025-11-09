import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


def process_excel_file(file_name: str, sheet_name: str) -> List[Dict[str, Any]]:
    """Process Excel file and convert to list of post dictionaries.

    Args:
        file_name: Path to the Excel file.
        sheet_name: Name of the sheet to read.

    Returns:
        List of dictionaries representing posts with categories and tags as lists.
    """
    # Load the Excel file
    df = pd.read_excel(file_name, sheet_name=sheet_name)

    # Convert the DataFrame to a list of dictionaries
    posts_data: List[Dict[str, Any]] = []
    for record in df.to_dict("records"):
        # Convert to Dict[str, Any] explicitly
        post: Dict[str, Any] = {}
        for key, value in record.items():
            post[str(key)] = value
        posts_data.append(post)

    # Iterate over the posts data and convert the 'categories' and 'tags' fields to lists
    for post in posts_data:
        post["categories"] = list(set(str(post["categories"]).split("|")))
        post["tags"] = list(set(str(post["tags"]).split("|")))

    return posts_data


def main() -> None:
    """Process Excel file to get posts data and save to JSON."""
    # Process Excel file to get posts data
    posts_data = process_excel_file("posts.xlsx", "Sheet1")

    # Save the data to a JSON file
    output_path = Path("posts_data.json")
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(posts_data, file, indent=4, ensure_ascii=False)
    logger.info("Posts data saved to %s", output_path)


if __name__ == "__main__":
    main()
