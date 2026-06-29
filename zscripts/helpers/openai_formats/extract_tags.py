import json

from bs4 import BeautifulSoup
from helpers.utilities.paths import org_path

# Define output directory
output_dir = str(org_path("Revenue Streams", "Blogs", "format_ai", "text_folder"))

# Load JSON file
with open(org_path("Revenue Streams", "Blogs", "format_ai", "all_posts.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

# Initialize two empty lists to separately store h2 and strong tags
h2_tags = []
strong_tags = []

# Loop over each blog
for blog in data.values():
    # Loop over each post
    for post in blog["posts"]:
        # Parse post content with BeautifulSoup
        soup = BeautifulSoup(post["content"], "html.parser")
        # Find all h2 and strong tags
        for h2_tag in soup.find_all("h2"):
            h2_tags.append(h2_tag.text)
        for strong_tag in soup.find_all("strong"):
            strong_tags.append(strong_tag.text)

# Convert lists to sets to remove duplicates, then convert back to list
h2_tags = list(set(h2_tags))
strong_tags = list(set(strong_tags))

# Write h2 tags to a .txt file
with open(output_dir + r"\h2_tags.txt", "w", encoding="utf-8") as f:
    for tag in h2_tags:
        f.write("%s\n" % tag)

# Write strong tags to a .txt file
with open(output_dir + r"\strong_tags.txt", "w", encoding="utf-8") as f:
    for tag in strong_tags:
        f.write("%s\n" % tag)
