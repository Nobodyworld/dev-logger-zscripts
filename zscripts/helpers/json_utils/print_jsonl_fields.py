import json

with open("stanfords.jsonl", "r") as f:
    for line in f:
        data = json.loads(line)
        print(data["input"])
        print(data["output"])
