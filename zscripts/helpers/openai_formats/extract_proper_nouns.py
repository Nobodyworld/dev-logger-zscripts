import json
from collections import Counter

import nltk
from bs4 import BeautifulSoup
from nltk import pos_tag
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize

# Download required NLTK data
nltk.download("punkt")
nltk.download("averaged_perceptron_tagger")
nltk.download("stopwords")

# Load the list of NLTK stopwords
stop_words = set(stopwords.words("english"))

# Create a custom blacklist of words to exclude
blacklist = {"word1", "word2"}

# Load JSON file
with open("all_posts.json") as f:
    data = json.load(f)

# Prepare a list to store the proper nouns
proper_nouns = []

# Iterate over the blog posts
for _blog_id, blog_info in data.items():
    # The "posts" field should be a list of posts, so we need to iterate over that list
    for post in blog_info["posts"]:
        # Extract post content
        blog_post = post["content"]

        # Remove HTML tags using BeautifulSoup
        soup = BeautifulSoup(blog_post, "html.parser")

        # Remove headers
        for header in soup(["h1", "h2", "h3", "h4", "h5", "h6"]):
            header.decompose()

        # Get the remaining text
        blog_post = soup.get_text()

        # Divide the text into sentences and then into words
        tokens = [word_tokenize(sent) for sent in sent_tokenize(blog_post)]

        # Flatten the list of tokens because POS tagging function expects a flat list
        tokens = [token for sublist in tokens for token in sublist]

        # Tag each token with its grammatical information
        tagged_tokens = pos_tag(tokens)

        # Extract proper nouns (names in most cases)
        post_proper_nouns = [token for token, pos in tagged_tokens if pos in ["NNP", "NNPS"]]

        # Filter proper nouns based on stopwords and the blacklist
        post_proper_nouns = [
            noun
            for noun in post_proper_nouns
            if noun.lower() not in stop_words and noun.lower() not in blacklist
        ]

        # Append the proper nouns from this post to the main list
        proper_nouns.extend(post_proper_nouns)

# Count the frequencies of each proper noun
proper_noun_counts = Counter(proper_nouns)

# Convert the counter to a list of (proper_noun, count) tuples
results = list(proper_noun_counts.items())

# Open the output file and write the results in JSON format
with open("output.json", "w") as outfile:
    json.dump(results, outfile)
