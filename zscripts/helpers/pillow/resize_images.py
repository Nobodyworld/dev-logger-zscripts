import os

from PIL import Image

# Set batch size, image dimensions
img_height = 384
img_width = 256

# Get the directory containing the script
script_dir = os.path.dirname(os.path.realpath(__file__))

# Iterate through images in script directory and resize them
for filename in os.listdir(script_dir):
    if filename.endswith(".jpg") or filename.endswith(".jpeg"):
        # Open the image and resize it
        image = Image.open(os.path.join(script_dir, filename))
        image = image.resize((img_width, img_height), Image.ANTIALIAS)

        # Save the resized image to the original directory with the same filename
        image.save(os.path.join(script_dir, filename), quality=100)

print("Resizing complete.")
