import json
import re

from bs4 import BeautifulSoup

input_file = "training_data.jsonl"
output_file = "training_data_cleaned.jsonl"


def remove_tags(content: str) -> str:
    # Remove <iframe> tags and content
    # TODO - add global path function
    iframe_pattern = r"<iframe\b[^>]*>.*?</iframe>"
    content = re.sub(iframe_pattern, "", content)

    # Remove <a> tags but keep the text within them
    soup = BeautifulSoup(content, "html.parser")
    for a_tag in soup.find_all("a"):
        a_tag.unwrap()
    content = str(soup)

    return content


with (
    open(input_file, "r", encoding="utf-8") as file,
    open(output_file, "w", encoding="utf-8") as output,
):
    for line in file:
        data_entry = json.loads(line.strip())
        title = data_entry["title"]
        before = data_entry["before"]
        after = data_entry["after"]

        before_cleaned = remove_tags(before)
        after_cleaned = remove_tags(after)

        data_entry_cleaned = {"title": title, "before": before_cleaned, "after": after_cleaned}
        output.write(json.dumps(data_entry_cleaned) + "\n")
