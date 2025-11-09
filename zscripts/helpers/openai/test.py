import os

from dotenv import load_dotenv

import openai

# Load the environment variables from the .env file
load_dotenv()

# Retrieve the API key from the environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set the API key for the openai package
openai.api_key = OPENAI_API_KEY

completion = openai.ChatCompletion.create(
    model="gpt-3.5-turbo", messages=[{"role": "user", "content": "Hello!"}]
)

print(completion.choices[0].message)
