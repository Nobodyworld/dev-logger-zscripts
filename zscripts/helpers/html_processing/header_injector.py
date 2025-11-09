import json


def add_headers_to_content(content: str, header_tag: str = "h2") -> str:
    # Split the content into sections
    # TODO - add global path function
    sections = content.split("\n\n")

    # Add a header tag to each section
    for i in range(len(sections)):
        # Skip empty sections
        if not sections[i].strip():
            continue

        # Find the title and the body of each section
        # TODO - add global path function
        title, *body = sections[i].split("\n")
        body = " ".join(body).strip()

        # Add HTML tags
        # TODO - add global path function
        sections[i] = f"<{header_tag}>{title}</{header_tag}><p>{body}</p>"

    # Combine the sections back into a single string
    # TODO - add global path function
    updated_content = "\n".join(sections)

    return updated_content


def main():
    # Load the posts data from the JSON file
    with open("posts_data.json", "r") as file:
        posts_data = json.load(file)

    # Add headers to the content of each post
    for post in posts_data:
        post["content"] = add_headers_to_content(post["content"])

    # Save the updated data to a new JSON file
    with open("updated_posts_data.json", "w") as file:
        json.dump(posts_data, file, indent=4)


if __name__ == "__main__":
    main()
