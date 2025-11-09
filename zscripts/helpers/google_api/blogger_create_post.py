# create_post.py
import json
from typing import Any, Dict

from no_post_blog_api.get_blogs_and_posts import service_setup

# If modifying these scopes, delete the file token.pickle.
# TODO - add global path function
SCOPES = ["https://www.googleapis.com/auth/blogger"]


def create_post(service: Any, blog_id: str, body: Dict[str, Any]) -> None:
    posts = service.posts()
    try:
        response = posts.insert(blogId=blog_id, body=body, isDraft=False).execute()
        print(f"Created post {response['id']} in blog {blog_id}")
    except Exception as e:
        print(e)


def main() -> None:
    service = service_setup()

    with open("drafts.json", "r", encoding="utf-8") as drafts_file:
        drafts: Dict[str, Dict[str, Any]] = json.load(drafts_file)

    for blog_id, blog in drafts.items():
        for post in blog.get("posts", []):
            create_post(service, blog_id, post)


if __name__ == "__main__":
    main()
