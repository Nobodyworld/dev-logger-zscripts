import json

from steps import steps

from helpers.utilities.paths import org_path

# Converting the steps to a JSON format
json_data = json.dumps(steps, indent=4)

# Save to a JSON file under organization storage
json_file = str(org_path("Core", "Command", "mnt", "data", "system_deployment_steps.json"))
with open(json_file, "w", encoding="utf-8") as file:
    file.write(json_data)

print("Wrote:", json_file)
