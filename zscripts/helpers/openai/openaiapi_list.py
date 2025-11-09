import os

from dotenv import load_dotenv

import openai

# Load the environment variables from the .env file
load_dotenv()

# Retrieve the API key from the environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set the API key for the openai package
openai.api_key = OPENAI_API_KEY

# List the available models
models = openai.Model.list()

# Write the list of models to a text file
with open("models_id.txt", "w") as f:
    for model in models["data"]:
        f.write(str(model["id"]))
        f.write("\n")
