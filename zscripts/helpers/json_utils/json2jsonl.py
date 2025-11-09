import json

with open("phonemes.json", "r") as f1, open("phonemes.jsonl", "w") as f2:
    data = json.load(f1)
    for obj in data:
        json.dump(obj, f2)
        f2.write("\n")
