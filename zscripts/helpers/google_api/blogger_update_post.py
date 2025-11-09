# update_post.py
import json
from typing import Any, Dict

from no_post_blog_api.get_blogs_and_posts import service_setup

# If modifying these scopes, delete the file token.pickle.
# TODO - add global path function
SCOPES = ["https://www.googleapis.com/auth/blogger"]


def patch_post(service: Any, blog_id: str, post_id: str, body: Dict[str, Any]) -> None:
    posts = service.posts()
    try:
        posts.patch(blogId=blog_id, postId=post_id, body=body).execute()
        print(f"Updated post {post_id} in blog {blog_id}")
    except Exception as e:
        print(e)


def main() -> None:
    service = service_setup()

    with open("drafts.json", "r", encoding="utf-8") as drafts_file:
        drafts: Dict[str, Dict[str, Any]] = json.load(drafts_file)

    for blog_id, blog in drafts.items():
        for post in blog.get("posts", []):
            if "id" in post:
                body = {"content": post.get("content", "")}
                patch_post(service, blog_id, post["id"], body)


if __name__ == "__main__":
    main()
