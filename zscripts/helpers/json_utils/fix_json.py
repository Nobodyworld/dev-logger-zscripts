import json

# Load the existing JSON data
with open("aesop.json", "r") as f:
    data = json.load(f)

# Open a new file to write the JSONL data
with open("aesop.jsonl", "w") as f:
    for story in data["stories"]:
        # Write each story as a separate line in the new file
        f.write(json.dumps(story) + "\n")
