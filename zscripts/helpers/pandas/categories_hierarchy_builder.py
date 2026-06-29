import json
import re

import pandas as pd


def build_json_from_excel(excel_file: str, sheet_name: str) -> None:
    """Build a nested JSON category tree from an Excel sheet and write to file."""
    # Read the Excel file into a pandas DataFrame
    df = pd.read_excel(excel_file, sheet_name=sheet_name)

    # Create a function to generate the slug for a category
    def generate_slug(name: str) -> str:
        # Convert the name to lowercase
        slug = name.lower()
        # Remove non-alphanumeric characters (replace with hyphen)
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        return slug

    # Initialize the hierarchical structure as a nested dictionary
    hierarchy = {}
    for _, row in df.iterrows():
        sector = row["Sector"]
        subsector = row["Subsector"]
        industry_group = row["Industry Group"]
        industry = row["Industry"]
        national_industry = row["National Industry"]

        # Generate the slugs for each category
        sector_slug = generate_slug(sector)
        subsector_slug = generate_slug(subsector)
        industry_group_slug = generate_slug(industry_group)
        industry_slug = generate_slug(industry)
        national_industry_slug = generate_slug(national_industry)

        # Build the hierarchy
        if sector not in hierarchy:
            hierarchy[sector] = {"slug": sector_slug}

        if subsector not in hierarchy[sector]:
            hierarchy[sector][subsector] = {"slug": subsector_slug}

        if industry_group not in hierarchy[sector][subsector]:
            hierarchy[sector][subsector][industry_group] = {"slug": industry_group_slug}

        if industry not in hierarchy[sector][subsector][industry_group]:
            hierarchy[sector][subsector][industry_group][industry] = {"slug": industry_slug}

        # Check if the National Industry is not empty
        if not pd.isnull(national_industry):
            # Append the National Industry under the corresponding Industry
            if "National Industry" not in hierarchy[sector][subsector][industry_group][industry]:
                hierarchy[sector][subsector][industry_group][industry]["National Industry"] = {}
            hierarchy[sector][subsector][industry_group][industry]["National Industry"][national_industry] = {
                "slug": national_industry_slug
            }

    # Convert the hierarchy dictionary to JSON
    json_data = json.dumps(hierarchy, indent=2)

    # Write the JSON data to a file
    with open("categories.json", "w") as json_file:
        json_file.write(json_data)

    print("JSON file created successfully!")


if __name__ == "__main__":
    excel_file = "categories.xlsx"  # Replace with the path to your Excel file
    sheet_name = "Sheet1"  # Replace with the sheet name containing the data

    build_json_from_excel(excel_file, sheet_name)
