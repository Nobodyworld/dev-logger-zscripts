import os
import urllib.request

import requests

from helpers.utilities.paths import org_path

api_key = os.environ.get("OPENAI_API_KEY", "")

# Path to the directory containing the image files
directory_path = str(org_path("Scripts", "image_gen_var"))

# list of image files in the directory
image_files = [f for f in os.listdir(directory_path) if f.endswith(".png")][:2]

for image_file in image_files:
    prompt = image_file.replace(".png", "")
    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": "image-alpha-001",
            "n": 1,
            "size": "1024x1024",
            "response_format": "url",
            "prompt": prompt,
        },
    )

    if response.status_code == 200:
        image_urls = [image["url"] for image in response.json()["data"]]
        for i, image_url in enumerate(image_urls):
            print(f"Image {i+1} generated successfully: {image_url}")

            # construct the file name
            file_name = os.path.splitext(image_file)[0] + f"_{i+1}.png"
            base_dir = org_path("Revenue Streams", "Etsy Shops", "Images (Unedited)")
            file_path = os.path.join(base_dir, file_name)

            # add a number to the end of the file name if the file already exists
            if os.path.exists(file_path):
                counter = 1
                while os.path.exists(file_path):
                    file_name = os.path.splitext(image_file)[0] + f"_{i+1}_{counter}.png"
                    file_path = os.path.join(base_dir, file_name)
                    counter += 1

            # download the image and save it to the specified file path
            urllib.request.urlretrieve(image_url, file_path)
    else:
        print(f"Failed to generate images for {image_file}: {response.text}")
