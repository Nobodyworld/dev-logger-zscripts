import json
import logging
import os
from typing import Any, Dict, List, Optional

import google.oauth2.credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Scopes required by the application
# TODO - add global path function
SCOPES = ["https://www.googleapis.com/auth/blogger"]


def service_setup() -> Any:
    creds = None
    token_path = "token.json"
    if os.path.exists(token_path):
        with open(token_path, "r") as token:
            creds_info = json.load(token)
            creds = google.oauth2.credentials.Credentials(**creds_info)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            json.dump(
                {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                },
                token,
            )
    return build("blogger", "v3", credentials=creds)


def create_post(service: Any, blog_id: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    posts = service.posts()
    try:
        response = posts.insert(blogId=blog_id, body=body, isDraft=False).execute()
        return response
    except Exception as e:
        logging.error("Failed to create post: %s", e)
        return None


def update_post(
    service: Any, blog_id: str, post_id: str, body: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    posts = service.posts()
    try:
        response = posts.update(blogId=blog_id, postId=post_id, body=body).execute()
        return response
    except Exception as e:
        logging.error("Failed to update post: %s", e)
        return None


def get_blogs(service: Any) -> List[Dict[str, Any]]:
    blogs = service.blogs()
    try:
        return blogs.listByUser(userId="self").execute().get("items", [])
    except Exception as e:
        logging.error("Failed to retrieve blogs: %s", e)
        return []


def get_posts(service: Any, blog_id: str) -> List[Dict[str, Any]]:
    posts = service.posts()
    request = posts.list(blogId=blog_id)
    post_details = []

    while request is not None:
        try:
            response = request.execute()
            post_details.extend(extract_post_details(response))
            request = posts.list_next(request, response)
        except Exception as e:
            logging.error("Failed to list posts: %s", e)
            break

    return post_details


def extract_post_details(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "kind": "blogger#post",
            "id": post["id"],
            "title": post["title"],
            "content": post["content"],
            "labels": post.get("labels", []),
            "customMetaData": post.get("customMetaData", ""),
            "searchDescription": post.get("searchDescription", ""),
        }
        for post in response.get("items", [])
    ]


def save_to_file(blog_posts: Dict[str, Any]) -> None:
    with open("all_posts.json", "w", encoding="utf-8") as f:
        json.dump(blog_posts, f, ensure_ascii=False, indent=4)


def main() -> None:
    service = service_setup()
    blogs = get_blogs(service)
    blog_posts = {}

    exclude_blogs = [
        "6213158991640960695",
        "2781154189089618398",
        "Keep Up Jones",
        "Organization World",
    ]

    for blog in blogs:
        if blog["id"] in exclude_blogs or blog["name"] in exclude_blogs:
            continue
        blog_posts[blog["id"]] = {"name": blog["name"], "posts": get_posts(service, blog["id"])}

    save_to_file(blog_posts)


if __name__ == "__main__":
    main()
