import os
from pathlib import Path
from urllib.parse import urlparse

import requests

from zscripts.helpers.utilities.paths import org_path

api_key = os.environ.get("OPENAI_API_KEY", "")
REQUEST_TIMEOUT = 30

descriptions = ["image variation 1", "image variation 2", "image variation 3"]

for description in descriptions:
    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": "image-alpha-001",
            "prompt": description,
            "size": "1024x1024",
            "n": 1,
            "response_format": "url",
        },
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 200:
        image_urls = [image["url"] for image in response.json()["data"]]
        for i, image_url in enumerate(image_urls):
            print(f"Image {i+1} generated successfully: {image_url}")

            # construct the file name
            file_name = description.replace(" ", "_") + ".png"
            base_dir = org_path("Revenue Streams", "Etsy Shops", "Images (Unedited)")
            file_path = str(base_dir / file_name)

            # add a number to the end of the file name if the file already exists
            if os.path.exists(file_path):
                counter = 1
                while os.path.exists(file_path):
                    file_name = description.replace(" ", "_") + f"_{counter}.png"
                    file_path = str(base_dir / file_name)
                    counter += 1

            # download the image and save it to the specified file path
            parsed_url = urlparse(image_url)
            if parsed_url.scheme not in {"http", "https"}:
                raise ValueError(f"Unsupported image URL scheme: {parsed_url.scheme}")
            image_response = requests.get(image_url, timeout=REQUEST_TIMEOUT)
            image_response.raise_for_status()
            Path(file_path).write_bytes(image_response.content)
    else:
        print(f"Failed to generate images: {response.text}")
