import os

import requests

api_key = os.environ["YOUR_API_KEY"]
description = (
    "A Disco oil painting of an army of ducks, all marching in uniform, "
    "and formation on a hillside."
)

response = requests.post(
    "https://api.openai.com/v1/images/generations",
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    json={
        "model": "image-alpha-001",
        "prompt": description,
        "size": "1024x1024",
        "n": 2,
        "response_format": "url",
    },
)

if response.status_code == 200:
    image_urls = [image["url"] for image in response.json()["data"]]
    for i, image_url in enumerate(image_urls):
        print(f"Image {i+1} generated successfully: {image_url}")
else:
    print(f"Failed to generate images: {response.text}")
