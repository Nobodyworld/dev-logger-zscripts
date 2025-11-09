import os

from PyPDF2 import PdfReader

# Set the path of the directory containing PDF files
# TODO - add global path function
pdf_dir = r"\wiki\encyclopedia\jpegs\text"

# Loop through each file in the directory
for filename in os.listdir(pdf_dir):

    # Check if the file is a PDF
    if filename.endswith(".pdf"):
        try:
            # Open the PDF file
            with open(os.path.join(pdf_dir, filename), "rb") as pdf_file:
                # Read the PDF file
                pdf_reader = PdfReader(pdf_file)
                # Create a new file with the same name but with a .txt extension
                txt_file = open(
                    os.path.join(pdf_dir, os.path.splitext(filename)[0] + ".txt"),
                    "w",
                    encoding="utf-8",
                )
                # Loop through each page in the PDF file
                for page_num in range(len(pdf_reader.pages)):
                    # Extract the text from the page
                    text = pdf_reader.pages[page_num].extract_text()
                    # Write the text to the new file
                    txt_file.write(text)
                # Close the new file
                txt_file.close()
        except Exception as e:
            # If there is an error, print an error message with the file name and the error message
            print(f"Error processing file {filename}: {str(e)}")
