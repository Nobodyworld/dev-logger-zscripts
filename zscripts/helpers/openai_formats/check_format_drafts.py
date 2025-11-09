import json
from typing import Any, Dict

from bs4 import BeautifulSoup


def load_posts() -> Dict[str, Any]:
    with open("all_posts.json", "r") as file:
        return json.load(file)


def save_drafts(drafts: Dict[str, Any]) -> None:
    with open("drafts.json", "w") as file:
        json.dump(drafts, file, indent=2)


def check_format(post: str) -> bool:
    soup = BeautifulSoup(post, "html.parser")

    # Check if post starts with <p> and ends with <p> or <iframe>
    if not str(soup.contents[0]).startswith("<p>"):
        return False
    if not str(soup.contents[-1]).startswith("<p>") and not str(soup.contents[-1]).startswith(
        "<iframe"
    ):
        return False

    # Check for presence of headers
    headers = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    if not headers:
        return False

    return True


def main() -> None:
    posts = load_posts()
    drafts: Dict[str, Any] = {}

    for blog_id, blog in posts.items():
        blog_drafts = {"posts": []}
        for post in blog["posts"]:
            if not check_format(post["content"]):
                blog_drafts["posts"].append(post)
        if blog_drafts["posts"]:
            drafts[blog_id] = blog_drafts

    save_drafts(drafts)


if __name__ == "__main__":
    main()
