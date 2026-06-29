import os
from pathlib import Path
from urllib.parse import urlparse

import requests

from zscripts.helpers.utilities.paths import org_path

api_key = os.environ["YOUR_API_KEY"]
description = (
    "A Disco oil painting of an army of ducks, all marching in uniform, and formation on a hillside."
)
REQUEST_TIMEOUT = 30

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
    timeout=REQUEST_TIMEOUT,
)

if response.status_code == 200:
    image_urls = [image["url"] for image in response.json()["data"]]
    base_dir = org_path("Revenue Streams", "Etsy Shops", "Images (Unedited)")
    base_dir.mkdir(parents=True, exist_ok=True)
    for i, image_url in enumerate(image_urls):
        print(f"Image {i + 1} generated successfully: {image_url}")
        parsed_url = urlparse(image_url)
        if parsed_url.scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported image URL scheme: {parsed_url.scheme}")
        image_response = requests.get(image_url, timeout=REQUEST_TIMEOUT)
        image_response.raise_for_status()
        Path(base_dir / f"image_{i + 1}.png").write_bytes(image_response.content)
else:
    print(f"Failed to generate images: {response.text}")
