import os

import cv2

# Define minimum blemish size (in pixels)
min_blemish_size = 20

# Define blending strength (between 0 and 1)
blend_strength = 0.75

# Define mask threshold value (between 0 and 255)
mask_threshold = 150

# Get the path to the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Loop over all JPEG files in the script's directory
for filename in os.listdir(script_dir):
    if filename.endswith(".jpg") or filename.endswith(".jpeg"):
        # Load image file
        img_file = os.path.join(script_dir, filename)
        try:
            img = cv2.imread(img_file)
        except Exception as e:
            print(f"Error loading image file {img_file}: {str(e)}")
            continue

        # Apply median blur to remove noise
        blur = cv2.medianBlur(img, 3)

        # Convert blurred image to grayscale
        gray = cv2.cvtColor(blur, cv2.COLOR_BGR2GRAY)

        # Apply adaptive thresholding to segment image into foreground and background
        blockSize = 51  # Increasing this parameter
        C = 20  # Decreasing this parameter
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize, C
        )

        # Create a mask by thresholding the grayscale image
        mask = cv2.threshold(gray, mask_threshold, 255, cv2.THRESH_BINARY_INV)[1]

        # Apply the mask to the thresholded image
        thresh_masked = cv2.bitwise_and(thresh, thresh, mask=mask)

        # Find contours in thresholded image
        try:
            contours, _ = cv2.findContours(thresh_masked, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        except Exception as e:
            print(f"Error finding contours in image file {img_file}: {str(e)}")
            continue

        # Loop over contours and remove small blemishes
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_blemish_size:
                cv2.drawContours(thresh_masked, [cnt], -1, (0, 0, 0), -1)

        # Invert thresholded image
        thresh_inv = cv2.bitwise_not(thresh_masked)

        # Convert thresholded image to color
        thresh_color = cv2.cvtColor(thresh_inv, cv2.COLOR_GRAY2BGR)

        # Blend thresholded image with original image
        result = cv2.addWeighted(img, 1 - blend_strength, thresh_color, blend_strength, 0)

        # Save result to

        # Save result to output file
        try:
            cv2.imwrite(img_file, result)
        except Exception as e:
            print(f"Error saving image file {img_file}: {str(e)}")
            continue

        # Print progress
        print(f"Processed image file {img_file}")
