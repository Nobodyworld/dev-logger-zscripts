import json
import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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


def create_wordpress_post(
    title: str, content: str, categories: list[str], tags: list[str], status: str = "publish"
) -> Optional[dict[str, Any]]:
    """Create a WordPress post with categories/tags; create tags if needed."""
    url = f"{base_url}/posts"
    try:
        headers = {"User-Agent": "python-requests/2.x", "Content-Type": "application/json"}

        # Get category IDs from category names
        category_ids: list[int] = []
        for category_name in categories:
            category_url = f"{base_url}/categories?slug={category_name}"
            category_response = requests.get(
                category_url,
                auth=(wordpress_username or "", wordpress_password or ""),
                headers=headers,
            )
            if category_response.status_code == 200:
                category_data = category_response.json()
                if category_data:
                    category_ids.append(category_data[0]["id"])

        # Get tag IDs from tag names, create if they don't exist
        tag_ids: list[int] = []
        for tag_name in tags:
            tag_url = f"{base_url}/tags?slug={tag_name}"
            tag_response = requests.get(
                tag_url, auth=(wordpress_username or "", wordpress_password or ""), headers=headers
            )
            if tag_response.status_code == 200:
                tag_data = tag_response.json()
                if tag_data:
                    tag_ids.append(tag_data[0]["id"])
                else:
                    tag_data = {"name": tag_name, "slug": tag_name}
                    tag_create_response = requests.post(
                        f"{base_url}/tags",
                        auth=(wordpress_username or "", wordpress_password or ""),
                        headers=headers,
                        json=tag_data,
                    )
                    if tag_create_response.status_code == 201:
                        tag_data = tag_create_response.json()
                        tag_ids.append(tag_data["id"])

        data = {
            "title": title,
            "content": content,
            "status": status,
            "categories": category_ids,
            "tags": tag_ids,
        }

        response = requests.post(
            url,
            auth=(wordpress_username or "", wordpress_password or ""),
            headers=headers,
            json=data,
        )
        if response.status_code == 201:
            return response.json()
        print("Failed to create post. Status code:", response.status_code)
        return None
    except requests.RequestException as e:
        print("Error during API request:", e)
        return None


def main() -> None:
    """Create posts from posts_data.json and list existing posts."""
    with open("posts_data.json", "r", encoding="utf-8") as file:
        posts_data = json.load(file)

    posts = get_wordpress_posts()
    if posts is not None:
        print("Posts:")
        for post in posts:
            print(f"- {post['title']['rendered']} (ID: {post['id']})")

    for post_data in posts_data:
        title = post_data["title"]
        content = post_data["content"]
        categories = post_data["categories"]
        tags = post_data.get("tags", [])
        new_post = create_wordpress_post(title, content, categories, tags)
        if new_post is not None:
            print("New post created:")
            print(f"- {new_post['title']['rendered']} (ID: {new_post['id']})")


if __name__ == "__main__":
    main()
