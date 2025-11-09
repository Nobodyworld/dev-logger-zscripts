import json
import re
from typing import List


def check_content_tags(content: str) -> List[int]:
    # Split the content into sections by splitting on each <h2> tag
    sections = re.split(r"(?=<h2>)", content)

    # Keep track of sections without correct tags
    sections_without_tags = []

    # Check each section
    for i, section in enumerate(sections, 1):
        if not re.match(r"<h2>.*?</h2><p>.*?</p>", section):
            sections_without_tags.append(i)

    return sections_without_tags


def main():
    # Load the posts data from the JSON file
    with open("updated_posts_data_v2.json", "r") as file:
        posts_data = json.load(file)

    # Check the content of each post for correct HTML tags
    for post in posts_data:
        sections_without_tags = check_content_tags(post["content"])

        if sections_without_tags:
            title = post["title"]
            print(
                'The post titled "%s" has sections without correct HTML tags:' % title,
                sections_without_tags,
            )


if __name__ == "__main__":
    main()
