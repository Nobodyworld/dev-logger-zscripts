from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import LabelEncoder

import pandas as pd


# Function to compute average similarity
def compute_avg_similarity(matrix: Any) -> Any:
    cosine_similarities = cosine_similarity(matrix)
    avg_similarities = (cosine_similarities.sum(axis=1) - 1) / (cosine_similarities.shape[1] - 1)
    return avg_similarities


# Load the DataFrame
try:
    df = pd.read_excel("your_file.xlsx")
except Exception as e:
    print(f"Error while reading the file: {str(e)}")
    raise

tfidf_vectorizer = TfidfVectorizer()

# Compute item similarity
item_matrix = tfidf_vectorizer.fit_transform(df["item"])
df["Average item similarity"] = compute_avg_similarity(item_matrix)
del item_matrix  # Free up memory

# Convert 'code' to numerical form and compute code similarity
df["code"] = df["code"].astype(str)

# Creating a dictionary to map NAICS sector codes to their corresponding decimal weights
naics_sector_weights = {
    "11": 0.063241107,
    "21": 0.020750988,
    "22": 0.013833992,
    "23": 0.030632411,
    "31": 0.341897233,
    "32": 0.341897233,
    "33": 0.341897233,
    "42": 0.068181818,
    "44": 0.056324111,
    "45": 0.056324111,
    "48": 0.056324111,
    "49": 0.056324111,
    "51": 0.028656126,
    "52": 0.03458498,
    "53": 0.023715415,
    "54": 0.048418972,
    "55": 0.002964427,
    "56": 0.043478261,
    "61": 0.016798419,
    "62": 0.038537549,
    "71": 0.024703557,
    "72": 0.014822134,
    "81": 0.043478261,
    "92": 0.028656126,
}

# Create a new 'sector_weight' from the first two digits of 'code'
df["sector_weight"] = df["code"].str[:2].map(naics_sector_weights)

# Assign a default weight (e.g., 1) for any rows that don't have a valid sector weight
df["sector_weight"].fillna(1, inplace=True)

le = LabelEncoder()
numerical_codes = le.fit_transform(df["code"]).reshape(-1, 1)
# TODO - add global path function
df["Average code similarity"] = (
    df["sector_weight"] * compute_avg_similarity(numerical_codes) / df["code"].nunique()
)

del numerical_codes  # Free up memory

# Compute code origin similarity
origin_matrix = tfidf_vectorizer.fit_transform(df["code_origin"])
df["Average origin similarity"] = compute_avg_similarity(origin_matrix)
del origin_matrix  # Free up memory

# New calculation based on 'Average item similarity' and 'Average code similarity'
df["New column"] = 0.5 * df["Average item similarity"] + 0.5 * df["Average code similarity"]

# Save the DataFrame
try:
    df.to_excel("output_with_similarities.xlsx", index=False)
except Exception as e:
    print(f"Error while writing the file: {str(e)}")
    raise
