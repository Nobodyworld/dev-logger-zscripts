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
le = LabelEncoder()
numerical_codes = le.fit_transform(df["code"]).reshape(-1, 1)
# TODO - add global path function
df["Average code similarity"] = compute_avg_similarity(numerical_codes) / df["code"].nunique()
del numerical_codes  # Free up memory

# Compute code origin similarity
origin_matrix = tfidf_vectorizer.fit_transform(df["code_origin"])
df["Average origin similarity"] = compute_avg_similarity(origin_matrix)
del origin_matrix  # Free up memory

# Save the DataFrame
try:
    df.to_excel("output_with_similarities.xlsx", index=False)
except Exception as e:
    print(f"Error while writing the file: {str(e)}")
    raise
