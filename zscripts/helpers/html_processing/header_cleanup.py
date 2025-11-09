import json
import re


def change_long_headers_to_paragraphs(content: str) -> str:
    # Find all headers in the content
    # TODO - add global path function
    headers = re.findall(r"<h2>(.*?)</h2>", content, re.DOTALL)

    for header in headers:
        # Check if the header is more than 100 characters long
        if len(header) > 100:
            # If it is, replace the header tag with a paragraph tag
            # TODO - add global path function
            content = content.replace(f"<h2>{header}</h2>", f"<p>{header}</p>")

    return content


def main():
    # Load the posts data from the JSON file
    with open("updated_posts_data.json", "r") as file:
        posts_data = json.load(file)

    # Change long headers to paragraphs in the content of each post
    for post in posts_data:
        post["content"] = change_long_headers_to_paragraphs(post["content"])

    # Save the updated data to a new JSON file
    with open("updated_posts_data_v2.json", "w") as file:
        json.dump(posts_data, file, indent=4)


if __name__ == "__main__":
    main()
