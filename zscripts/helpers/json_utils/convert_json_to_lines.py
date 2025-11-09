import json

from helpers.utilities.paths import org_path

# Resolve input JSON path from organization storage
file_path = str(org_path("Shared Documents - GPTs", "steps.JSON"))

# Reading the JSON file
with open(file_path, "r", encoding="utf-8") as file:
    data = json.load(file)

# Convert to JSONL format (one JSON object per line)
jsonl_content = "\n".join(json.dumps(step, ensure_ascii=False) for step in data)

# Saving the JSONL content to a new file next to the source
jsonl_file_path = file_path.replace(".json", ".jsonl")
with open(jsonl_file_path, "w", encoding="utf-8") as jsonl_file:
    jsonl_file.write(jsonl_content)

print("Wrote:", jsonl_file_path)
