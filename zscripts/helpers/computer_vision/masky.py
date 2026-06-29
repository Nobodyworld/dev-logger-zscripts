import os

import cv2
from helpers.utilities.paths import org_path

# Set input and output directories via organization storage root
input_dir = str(org_path("projects", "masky", "input"))
output_dir = str(org_path("projects", "masky", "output"))

# Set threshold value for difference image
threshold = 25

# Create output directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Loop over all image pairs in the input directory
for filename in os.listdir(input_dir):
    if filename.endswith("_before.jpg"):
        # Load before and after images
        before = cv2.imread(os.path.join(input_dir, filename))
        after = cv2.imread(os.path.join(input_dir, filename.replace("_before.jpg", "_after.jpg")))

        # Convert to grayscale
        before_gray = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY)
        after_gray = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)

        # Calculate difference image
        diff = cv2.absdiff(before_gray, after_gray)

        # Apply threshold to create binary mask
        mask = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)[1]

        # Apply postprocessing to refine mask (e.g., fill small holes)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

        # Save mask to output directory using naming convention
        mask_filename = filename.replace("_before.jpg", "_mask.jpg")
        output_path = os.path.join(output_dir, mask_filename)
        cv2.imwrite(output_path, mask)

        # Print status statement
        print(f"Saved mask file to {output_path}")
