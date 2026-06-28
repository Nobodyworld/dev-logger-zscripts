import os
import re

import pandas as pd
from bs4 import BeautifulSoup
from helpers.utilities.paths import org_path


def add_hyperlinks(
    input_folder: str, output_folder: str, excel_file: str, max_ads: int, report_file: str
) -> None:
    try:
        # Load data from the Excel file
        df = pd.read_excel(excel_file)

        # Remove duplicates based on 'words' column
        df.drop_duplicates(subset="words", keep="first", inplace=True)

        # Convert dataframe to dictionary with 'words' as keys
        words_dict = df.set_index("words").to_dict("index")

        # Get a list of all HTML files in the input folder
        html_files = [f for f in os.listdir(input_folder) if f.endswith(".html")]

        # Iterate over each HTML file in the input folder
        for html_file in html_files:
            print(f"Processing {html_file}...")

            # Open and read the HTML file
            with open(os.path.join(input_folder, html_file), "r", encoding="utf-8") as f:
                html = f.read()

            # Parse the HTML content using BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # List to store words which have been linked already
            linked_words = []

            # Counter for number of ads added
            ads_count = 0

            # Iterate over each word and its corresponding data in the dictionary
            for word, data in words_dict.items():
                # If the maximum number of ads has been added, break from the loop
                if ads_count >= max_ads:
                    print(
                        "Maximum number of ads (%d) reached for %s. Moving on to next file.",
                        max_ads,
                        html_file,
                    )
                    break

                # Skip the word if it has been linked already
                if word in linked_words:
                    continue

                # Escape special characters in the word for regex pattern
                word_escaped = re.escape(word)

                # Create regex pattern for whole word match (case insensitive)
                # TODO - add global path function
                regex = re.compile(rf"\b{word_escaped}\b", flags=re.I)

                # Find all text in the HTML that matches the regex pattern
                for tag in soup.find_all(text=regex):
                    # If the word is not in any 'h2' tag (or nested inside 'h2' tag)
                    if "h2" not in [parent.name for parent in tag.find_parents()]:
                        # Define the replacement based on the parent tag of the matched word
                        new_word = (
                            data["with_strong"]
                            if tag.parent.name == "li" and tag.strip().startswith(word)
                            else data["code"]
                        )

                        # Replace the first instance of the word with the
                        # replacement in the HTML string
                        html = re.sub(rf"\b{word_escaped}\b", new_word, html, count=1, flags=re.I)

                        # Add the word to the linked words list
                        linked_words.append(word)

                        # Increment the ads counter
                        ads_count += 1

                        break  # break after first match

            # Write the modified HTML to a new file in the output folder
            with open(os.path.join(output_folder, html_file), "w", encoding="utf-8") as f:
                f.write(html)

            # Log the result
            # TODO - add global path function
            log_message = f"Finished processing {html_file}. {ads_count} ad(s) added.\n"
            print(log_message)
            with open(report_file, "a") as f:
                f.write(log_message)

    except Exception as e:
        print(f"An error occurred: {e}")


# Define input and output directories and Excel file path
input_folder = str(org_path("Revenue Streams", "Blogs", "format_ai", "after_mst"))
output_folder = str(org_path("Revenue Streams", "Blogs", "format_ai", "ads_after_mst"))
excel_file = str(org_path("Revenue Streams", "Blogs", "format_ai", "data.xlsx"))

# Maximum number of ads to add in each HTML file
max_ads = 15

# File to store the processing log
report_file = str(org_path("Revenue Streams", "Blogs", "format_ai", "ads_report.txt"))

# Add hyperlinks (ads) in HTML files
add_hyperlinks(input_folder, output_folder, excel_file, max_ads, report_file)
