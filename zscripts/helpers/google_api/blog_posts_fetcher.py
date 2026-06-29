import json
import os
import pickle  # nosec B403
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.pickle.
# TODO - add global path function
SCOPES = ["https://www.googleapis.com/auth/blogger"]


def service_setup() -> Any:
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)  # nosec B301
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    try:
        return build("blogger", "v3", credentials=creds)
    except Exception as e:
        print(e)
        return None


def create_post(service: Any, blog_id: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    posts = service.posts()
    try:
        response = posts.insert(blogId=blog_id, body=body, isDraft=False).execute()
        return response
    except Exception as e:
        print(e)
        return None


def update_post(service: Any, blog_id: str, post_id: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    posts = service.posts()
    try:
        response = posts.update(blogId=blog_id, postId=post_id, body=body).execute()
        return response
    except Exception as e:
        print(e)
        return None


def get_blogs(service: Any) -> List[Dict[str, Any]]:
    blogs = service.blogs()
    try:
        return blogs.listByUser(userId="self").execute().get("items", [])
    except Exception as e:
        print(e)
        return []


def get_posts(service: Any, blog_id: str) -> List[Dict[str, Any]]:
    posts = service.posts()
    request = posts.list(blogId=blog_id)

    post_details = []
    while request is not None:
        try:
            response = request.execute()
            if "items" in response:
                for post in response["items"]:
                    post_detail = {
                        "kind": "blogger#post",
                        "id": post["id"],
                        "title": post["title"],
                        "content": post["content"],
                    }
                    if "labels" in post:
                        post_detail["labels"] = post["labels"]
                    if "customMetaData" in post:
                        post_detail["customMetaData"] = post["customMetaData"]
                    if "searchDescription" in post:
                        post_detail["searchDescription"] = post["searchDescription"]
                    post_details.append(post_detail)

            request = posts.list_next(request, response)

        except Exception as e:
            print(e)
            request = None

    return post_details


def save_to_file(blog_posts: Dict[str, Any]) -> None:
    with open("all_posts.json", "w", encoding="utf-8") as f:
        json.dump(blog_posts, f, ensure_ascii=False, indent=4)


def main() -> None:
    service = service_setup()
    blogs = get_blogs(service)
    blog_posts = {}

    # IDs or names of blogs to exclude
    exclude_blogs = [
        "6213158991640960695",
        "2781154189089618398",
        "Keep Up Jones",
        "Organization World",
    ]

    for blog in blogs:
        # Skip the blog if its ID or name is in the exclude_blogs list
        if blog["id"] in exclude_blogs or blog["name"] in exclude_blogs:
            continue

        blog_posts[blog["id"]] = {
            "name": blog["name"],
            "posts": get_posts(service, blog["id"]),
        }

    save_to_file(blog_posts)


if __name__ == "__main__":
    main()
