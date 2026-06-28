import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# WordPress credentials and API base
wordpress_username = os.getenv("WORDPRESS_USERNAME")
wordpress_password = os.getenv("WORDPRESS_PASSWORD")
base_url = "https://yayay.ai/wp-json/wp/v2"
REQUEST_TIMEOUT = 30


def get_wordpress_categories() -> Optional[list[dict[str, Any]]]:
    """Fetch categories from WordPress REST API using basic auth."""
    url = f"{base_url}/categories"
    try:
        headers = {"User-Agent": "python-requests/2.x"}
        response = requests.get(
            url,
            auth=(wordpress_username or "", wordpress_password or ""),
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        print("Failed to get categories. Status code:", response.status_code)
        return None
    except requests.RequestException as e:
        print("Error during API request:", e)
        return None


def main() -> None:
    """Print category names and IDs from WordPress."""
    categories = get_wordpress_categories()
    if categories is not None:
        print("Categories:")
        for category in categories:
            print(f"- {category['name']} (ID: {category['id']})")


if __name__ == "__main__":
    main()
