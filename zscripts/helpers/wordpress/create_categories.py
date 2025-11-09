import json
import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

wordpress_username = os.getenv("WORDPRESS_USERNAME")
wordpress_password = os.getenv("WORDPRESS_PASSWORD")
base_url = "https://yayay.ai/wp-json/wp/v2"


def get_wordpress_categories() -> Optional[list[dict[str, Any]]]:
    """Fetch WordPress categories via REST API."""
    url = f"{base_url}/categories"
    try:
        headers = {"User-Agent": "python-requests/2.x"}
        response = requests.get(
            url, auth=(wordpress_username or "", wordpress_password or ""), headers=headers
        )
        if response.status_code == 200:
            return response.json()
        print("Failed to get categories. Status code:", response.status_code)
        return None
    except requests.RequestException as e:
        print("Error during API request:", e)
        return None


def create_wordpress_category(
    name: str, slug: Optional[str] = None, parent: Optional[int] = None
) -> Optional[dict[str, Any]]:
    """Create a WordPress category if it doesn't already exist."""
    existing_categories = get_wordpress_categories() or []
    for category in existing_categories:
        if category.get("name") == name and category.get("parent") == parent:
            print(f"Category '{name}' with parent ID '{parent}' already exists. Skipping.")
            return category

    url = f"{base_url}/categories"
    try:
        headers = {"User-Agent": "python-requests/2.x", "Content-Type": "application/json"}
        data: Dict[str, Any] = {"name": name, "slug": slug, "parent": parent}
        response = requests.post(
            url,
            auth=(wordpress_username or "", wordpress_password or ""),
            headers=headers,
            json=data,
        )
        if response.status_code == 201:
            return response.json()
        print(f"Failed to create category '{name}'. Status code:", response.status_code)
        return None
    except requests.RequestException as e:
        print("Error during API request:", e)
        return None


def create_categories_recursive(
    data: Dict[str, Dict[str, Any]], parent_id: Optional[int] = None
) -> None:
    """Recursively create categories from a nested mapping."""
    if not data:
        return None

    for name, item_data in data.items():
        slug = item_data.get("slug", "")
        category = create_wordpress_category(name, slug=slug, parent=parent_id)
        if category:
            print(f"Created category: {name} (ID: {category['id']})")
            create_categories_recursive(item_data, parent_id=category["id"])


def main() -> None:
    """Load categories.json and create categories accordingly."""
    with open("categories.json", "r", encoding="utf-8") as json_file:
        categories_data: Dict[str, Dict[str, Any]] = json.load(json_file)

    if categories_data:
        print("Creating categories...")
        create_categories_recursive(categories_data)


if __name__ == "__main__":
    main()
