import os
import urllib.request

import requests

from helpers.utilities.paths import org_path

api_key = os.environ.get("OPENAI_API_KEY", "")
description = "Oil painting forest scene, natural colors, t"

response = requests.post(
    "https://api.openai.com/v1/images/generations",
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    json={
        "model": "image-alpha-001",
        "prompt": description,
        "size": "1024x1024",
        "n": 1,
        "response_format": "url",
    },
)

if response.status_code == 200:
    image_urls = [image["url"] for image in response.json()["data"]]
    base_dir = org_path("Revenue Streams", "Etsy Shops", "Images (Unedited)")
    for i, image_url in enumerate(image_urls):
        print(f"Image {i+1} generated successfully: {image_url}")

        # construct the file name and ensure uniqueness
        file_name = description.replace(" ", "_") + ".png"
        file_path = base_dir / file_name
        counter = 1
        while os.path.exists(file_path):
            file_name = description.replace(" ", "_") + f"_{counter}.png"
            file_path = base_dir / file_name
            counter += 1

        # download the image and save it to the specified file path
        urllib.request.urlretrieve(image_url, str(file_path))
else:
    print(f"Failed to generate images: {response.text}")
