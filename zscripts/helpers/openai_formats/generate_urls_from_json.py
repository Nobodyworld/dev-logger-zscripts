import json
import re
from typing import List


def generate_urls_from_file(input_file: str) -> List[str]:
    with open(input_file, "r") as f:
        data = json.load(f)

    urls: List[str] = []
    for blog_id in data:
        for post in data[blog_id]["posts"]:
            # Extract post details
            blog_name = data[blog_id]["name"]
            post_title = post["title"]
            labels = ", ".join(post.get("labels", []))  # Assumes 'labels' is a list

            # TODO - add global path function
            url = f"https://draft.blogger.com/u/1/blog/post/edit/{blog_id}/{post['id']}?hl=en-GB"

            # Extract ad scripts
            content = post.get("content", "")
            # TODO - add global path function
            ads = re.findall(r"(<iframe.*?</iframe>)", content, re.DOTALL)
            ads_str = " ".join(ads)

            # Remove ads from content
            for ad in ads:
                content = content.replace(ad, "")

            # TODO - add global path function
            content = content.replace("\n", " ")  # Remove newline characters from content

            # Extract analysis
            analysis = post.get(
                "analysis", "No analysis available"
            )  # Get analysis if it exists, otherwise default to 'No analysis available'
            # TODO - add global path function
            analysis = analysis.replace("\n", " ")  # Remove newline characters

            details = (
                f"Blog Name: {blog_name} ~ Post Title: {post_title} ~ Labels: {labels} ~ Content: {content}"
            )
            urls.append(f"{details} ~ {url} ~ {ads_str} ~ {analysis}")

    return urls


def write_urls_to_file(urls: List[str], output_file: str) -> None:
    with open(output_file, "w") as f:
        for url in urls:
            f.write(url + "\n")


def main() -> None:
    urls = generate_urls_from_file("all_posts.json")
    write_urls_to_file(urls, "urls.txt")


if __name__ == "__main__":
    main()
