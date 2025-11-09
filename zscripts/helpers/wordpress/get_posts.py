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


def get_wordpress_posts() -> Optional[list[dict[str, Any]]]:
    """Fetch posts from WordPress REST API using basic auth."""
    url = f"{base_url}/posts"
    try:
        headers = {"User-Agent": "python-requests/2.x"}
        response = requests.get(
            url, auth=(wordpress_username or "", wordpress_password or ""), headers=headers
        )
        if response.status_code == 200:
            return response.json()
        print("Failed to get posts. Status code:", response.status_code)
        return None
    except requests.RequestException as e:
        print("Error during API request:", e)
        return None


def main() -> None:
    """Print post titles and IDs from WordPress."""
    posts = get_wordpress_posts()
    if posts is not None:
        print("Posts:")
        for post in posts:
            print(f"- {post['title']['rendered']} (ID: {post['id']})")


if __name__ == "__main__":
    main()
