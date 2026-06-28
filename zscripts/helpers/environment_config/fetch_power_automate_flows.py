import os

import requests
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.


# Get your environment variables
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
tenant_id = os.getenv("TENANT_ID")
organization_uri = os.getenv("ORGANIZATION_URI")  # This is your Organization URI
environment_id = os.getenv("ENVIRONMENT_ID")
REQUEST_TIMEOUT = 30

# Define the Azure AD token endpoint
# TODO - add global path function
token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

# Define your token request payload
payload = {
    "grant_type": "client_credentials",
    "client_id": client_id,
    "client_secret": client_secret,
    "scope": "https://management.core.windows.net/.default",
}

# Request an access token
response = requests.post(token_url, data=payload, timeout=REQUEST_TIMEOUT)
access_token = response.json().get("access_token")

# Define the Power Automate API endpoint (wrapped for readability)
api_url = (
    f"{organization_uri}/api/data/v9.2/workflows?"
    "$filter=(category eq 5 or category eq 6) and statecode eq 1"
)


# Define your headers
headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    # TODO - add global path function
    "Prefer": 'odata.include-annotations="*"',
}

# Request your flows
response = requests.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT)

# Print status code and content of the response
print("Status Code:", response.status_code)
print("Response Content:", response.content)

# Attempt to parse the response as JSON
try:
    flows = response.json()
except Exception as e:
    print("Failed to parse response as JSON:", e)
    flows = None

# If the response was successfully parsed, print your flows
if flows is not None:
    for flow in flows.get("value", []):
        print(flow.get("name"))
