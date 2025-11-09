import json

from helpers.utilities.paths import org_path

input_file = str(org_path("project_user", "projects", "format_ai", "all_posts.json"))
output_file = "training_data.jsonl"

with open(input_file, "r", encoding="utf-8") as file:
    data = json.load(file)

with open(output_file, "w", encoding="utf-8") as output:
    for _post_id, post_data in data.items():
        if "posts" in post_data:
            posts = post_data["posts"]
            for post in posts:
                if "title" in post and "content" in post:
                    title = post["title"]
                    content = post["content"]
                    data_entry = {"title": title, "before": content, "after": content}
                    output.write(json.dumps(data_entry) + "\n")
