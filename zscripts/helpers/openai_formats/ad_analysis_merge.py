import json
import re


def clean_title(title: str) -> str:
    """Normalize a title to lowercase words separated by single spaces."""
    return re.sub(r"\W+", " ", title).strip().lower()


# load the json file
with open("all_posts.json", "r") as f:
    data = json.load(f)

# open the text file and read its content
with open("ad_analysis.txt", "r") as f:
    txt = f.read()

# split by the conversation separator, i.e., double new line
# TODO - add global path function
conversations = txt.split("\n\n")

# regex pattern to get the blog title from the analysis
pattern = r'^"(.*?)"'

count = 0  # counter for how many analyses are added
titles_not_found = []  # list to store titles that are not found in the json data

# loop over the conversations
for conversation in conversations:
    # split the conversation by 'From a behavioral' to separate the title and the analysis
    # TODO - add global path function
    parts = re.split(r"\nFrom a behavioral", conversation, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) < 2:
        continue
    title, analysis = parts
    title = title.strip()  # remove leading/trailing whitespace

    # extract the blog title from the analysis
    match = re.search(pattern, title)
    if not match:
        continue
    title = clean_title(match.group(1))

    # loop over the blogs in the json data
    found = False  # flag to check if the title is found in the json data
    for blog in data.values():
        # loop over the posts in the blog
        for post in blog["posts"]:
            # normalize the post title
            post_title = clean_title(post["title"])
            # if the title matches with the post title, add the analysis to the post
            if post_title == title:
                post["analysis"] = analysis.strip()
                count += 1  # increment the counter
                found = True  # set the flag to True
                break
        if found:
            break

    if not found:
        titles_not_found.append(title)

# save the updated json data
with open("all_posts.json", "w") as f:
    json.dump(data, f, indent=4)

print(f"Total analyses added: {count}")  # print the total count
print(
    f"Titles not found in JSON data: {titles_not_found}"
)  # print the titles not found in the json data
