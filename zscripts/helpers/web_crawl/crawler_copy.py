################################################################################
### Step 1
################################################################################

import os
import re
import time
import urllib.request
import urllib.robotparser
from collections import deque
from html.parser import HTMLParser
from typing import List
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

# Regex pattern to match a URL
# TODO - add global path function
HTTP_URL_PATTERN = r"^http[s]*://.+"
REQUEST_TIMEOUT = 20

# Define root domain to crawl
domain = "lakewoodforestfund.com"
# TODO - add global path function
full_url = "http://www.lakewoodforestfund.com/welcome.html"


# Create a class to parse the HTML and get the hyperlinks
class HyperlinkParser(HTMLParser):
    """HTML parser that collects hyperlink hrefs."""

    def __init__(self) -> None:
        """Initialize storage for collected hyperlinks."""
        super().__init__()
        self.hyperlinks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str]]) -> None:
        """Collect href attribute from anchor tags."""
        attrs_dict = dict(attrs)
        if tag == "a" and "href" in attrs_dict:
            self.hyperlinks.append(attrs_dict["href"])


################################################################################
### Step 2
################################################################################


def get_hyperlinks(url: str) -> List[str]:
    # Try to open the URL and read the HTML
    try:
        # Open the URL and read the HTML
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:  # nosec B310
            # If the response is not HTML or is a PDF, return an empty list
            content_type = response.info().get("Content-Type")
            if not content_type or not content_type.startswith("text/html"):
                return []

            # Decode the HTML
            html = response.read().decode("utf-8")
    except Exception as e:
        print(e)
        return []

    # Create the HTML Parser and then Parse the HTML to get hyperlinks
    parser = HyperlinkParser()
    parser.feed(html)
    return parser.hyperlinks


################################################################################
### Step 3
################################################################################


# Function to get the hyperlinks from a URL that are within the same domain
def get_domain_hyperlinks(local_domain: str, url: str) -> List[str]:
    clean_links: List[str] = []

    # Parse the URL and get the domain
    domain = urlparse(url).netloc

    # Check the robots.txt file to see if crawling is allowed
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"https://{domain}/robots.txt")
    rp.read()

    for link in set(get_hyperlinks(url)):
        clean_link = None

        # If link is a URL, ensure same domain and allowed by robots.txt
        if re.search(HTTP_URL_PATTERN, link):
            url_obj = urlparse(link)
            if url_obj.netloc == local_domain and rp.can_fetch("*", link):
                clean_link = link

        # If the link is not a URL, check if it is a relative link
        else:
            if link.startswith("/"):
                link = link[1:]
            elif link.startswith("#") or link.startswith("mailto:"):
                continue
            clean_link = f"https://{local_domain}/{link}"

        if clean_link is not None:
            if clean_link.endswith("/"):
                clean_link = clean_link[:-1]
            clean_links.append(clean_link)

    return list(set(clean_links))


################################################################################
### Step 4
################################################################################


def crawl(url: str) -> None:
    # Parse the URL and get the domain
    local_domain = urlparse(url).netloc

    # Create a queue to store the URLs to crawl
    queue = deque([url])

    # Create a set to store the URLs that have already been seen (no duplicates)
    seen = {url}

    # Create a directory to store the text files
    if not os.path.exists("text/"):
        os.mkdir("text/")

    if not os.path.exists(f"text/{local_domain}/"):
        os.mkdir(f"text/{local_domain}/")

    # Create a directory to store the csv files
    if not os.path.exists("processed"):
        os.mkdir("processed")

    # Define headers to mimic a regular browser
    headers = {"User-Agent": "python-requests/2.x"}

    # Define a delay between requests to avoid triggering the server's rate limit
    delay = 1  # in seconds

    # While the queue is not empty, continue crawling
    while queue:
        # Get the next URL from the queue
        url = queue.pop()
        print(url)

        # Save text from the url to a <url>.txt file
        # TODO - add global path function
        filename = unquote(url.split("?")[0].split("/")[-1].replace("=", "_"))
        with open(os.path.join("text", local_domain, f"{filename}.txt"), "w", encoding="UTF-8") as f:
            # Get the text from the URL using BeautifulSoup
            soup = BeautifulSoup(
                requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT).text,
                "html.parser",
            )

            # Check if the page requires JavaScript to run
            if "You need to enable JavaScript to run this app." in soup.get_text():
                print(f"Skipping page {url} due to JavaScript being required")
                continue

            # Get the text but remove the tags
            text = soup.get_text()

            # Otherwise, write the text to the file in the text directory
            f.write(text)

        # Get the hyperlinks from the URL and add them to the queue
        for link in get_domain_hyperlinks(local_domain, url):
            if link not in seen:
                queue.append(link)
                seen.add(link)

        # Add a delay to avoid triggering the server's rate limit
        time.sleep(delay)


crawl(full_url)
