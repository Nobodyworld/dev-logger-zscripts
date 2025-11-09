import re
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import pandas as pd

keyword_table = {
    "11": [
        "agriculture",
        "forestry",
        "fishing",
        "hunting",
        "farming",
        "agricultural",
        "groves",
        "tangelo",
        "tangerine",
        "grapefruit",
        "lemon",
        "citrus",
        "lime",
        "eggplants",
        "swine",
        "hay farming",
        "cereals",
        "pulses",
        "agave",
        "swine pigs",
        "asparagus",
        "cabbages",
        "spinach",
        "artichokes",
        "eggplants" "aubergines",
        "tomatoes",
        "garlic",
        "onions",
        "avocados",
        "grapes",
        "berries",
        "potatoes",
        "wheat",
        "maize",
        "corn",
        "sorghum",
        "barley",
        "soya beans",
        "groundnuts",
        "cottonseed",
        "canola",
        "olives",
        "coffee, green",
        "melons",
        "fruit-bearing vegetables",
        "raw milk",
        "natural honey",
        "processed poultry",
        "fluid milk",
        "dairy product substitutes",
        "citrus fruits",
        "coconuts, in shell",
        "sugar crops",
        "other live animals, except household pets",
        "vegetable seeds, except beet seeds",
        "fruit seeds",
        "other ruminants",
        "cattle",
        "fish, live",
        "rice",
        "other oilseeds",
    ],
    "21": [
        "mining",
        "quarrying",
        "oil",
        "gas",
        "extraction",
        "petrochemicals",
        "softwood logs",
        "hardwood logs",
    ],
    "22": [
        "utilities",
        "electricity",
        "water plant",
        "sewerage",
        "sewage",
        "waste treatment",
        "recycling",
    ],
    "23": [
        "construction",
        "contractors",
        "contracting",
        "builders",
        "building",
        "renovation",
        "renovators",
        "renovating",
        "renoval",
        "custom builders",
        "home builders",
        "locating underground utility lines prior to digging",
    ],
    "32": [
        "manufacturing",
        "production",
        "fabrication",
        "mfpm",
        "-mfpm",
        "breakfast cereal, except infant cereal",
        "yogurt, except frozen",
        "creamery butter",
        "cheese, including cottage cheese",
        "lard",
        "candles, including tapers",
        "power-driven handtools",
        "carbon black, all processes",
        "pallets",
        "adhesives",
        "rebuilt motor vehicle drive train components",
        (
            "acyclic hydrocarbons (e.g., butene, ethylene, propene) (except acetylene) "
            "made from refined petroleum or liquid hydrocarbons"
        ),
        "processed meat",
        "yarns",
        "pulp",
        "storage batteries",
        "rebuilt electrical system components",
    ],
    "42": [
        "wholesale",
        "wholesalers",
        "trade",
        "merchants",
        "merchant",
        "snack foods, except cakes and pastries, frozen goods, and dried fruits",
        "perishable prepared foods",
        "green leguminous vegetables",
        "specialty pet feed",
        "used rare collectors",
        "collectors' items",
    ],
    "44": [
        "retail",
        "trade",
        "store",
        "stores",
        "merchants",
        "shops",
        "shopping",
        "retailing",
        "retailers",
        "retailers",
        "retailer",
        "retailor",
        "bath linens",
        "bed linens",
        "access to laundry machines",
    ],
    "48": [
        "transportation",
        "warehousing",
        "freight",
        "-mfpm",
        "shipping",
        "logistics",
        "courier",
        "couriers",
        "couriering",
        "couriered",
        "courier",
        "pumping station",
        "cruises",
        "domestic, scheduled passenger transportation by air, coach class",
        "international, scheduled passenger transportation by air, coach class",
        "aircraft",
    ],
    "51": [
        "information",
        "publishing",
        "broadcasting",
        "telecommunications",
        "newspapers",
        "specialty content",
        "audio recordings, except audio books",
        "published applications software",
        "feature syndicates (i.e., advice columns, comic, news)",
        "pre-paid calling cards, telecommunications resellers",
        (
            "online access service providers, using client-supplied telecommunications "
            "(e.g., dial-up isps)"
        ),
        "voip service providers, using client-supplied telecommunications connections",
        "published system software",
        "internet advertising",
        "application service provisioning",
    ],
    "52": [
        "finance",
        "insurance",
        "banking",
        "investments",
        "securities",
        "funds",
        "trusts",
        "loans",
        "lending",
        "credit",
        "financing",
        "lending",
        "consumer loans, except mortgage and vehicle loans",
        "franchising agreements",
        "deposit account service packages, except business",
        "loans to financial businesses",
        "loans to non-financial businesses",
        "loans to governments",
        "financing related to securities",
        "home mortgage financing",
        "consumer vehicle loans",
        "mortgage banking (i.e., nondepository mortgage lending)",
        "collateralized mortgage obligation (cmo) issuing, private",
        "tax liens dealing",
        "certified financial planners, customized, fees paid by client",
        "business start-up fundraising using a crowdfunding platform",
        "collateralized mortgage obligations",
    ],
    "53": [
        "real estate",
        "rental",
        "leasing",
        "land purchase",
        "trademark licensing",
        "leased display advertising media space",
        "lodging reservation service",
    ],
    "54": [
        "professional",
        "scientific",
        "technical",
        "appraisal",
        "offices",
        "private practices",
        "lawyers",
        "law",
        "attorneys",
        "attorney",
        "lawyer",
        "legal",
        "accountants",
        "accounting",
        "bookkeeping",
        "exam preparation courses",
        "personal background checks",
        "outplacement/career counseling",
        "evaluation of environmental studies",
    ],
    "55": [
        "management",
        "companies",
        "enterprises",
        "agreement corporations",
        "corporation",
        "corporations",
        "incorporated",
        "incorporation",
        "incorporations",
    ],
    "56": ["administrative", "support", "waste", "management", "remediation"],
    "61": [
        "educational",
        "education",
        "training",
        "schools",
        "school",
        "college",
        "university",
        "universities",
        "academy",
        "academies",
        "colleges",
        "textbooks",
    ],
    "62": ["health", "care", "social", "assistance", "hospitals", "hospital"],
    "71": [
        "arts",
        "entertainment",
        "recreation",
        "casinos",
        "motel",
        "motels",
        "hotels",
        "hotel",
        "lodging",
        "camping",
        "amusement",
        "campground",
        "camp",
        "motor inns",
        "admissions to film exhibitions",
        "musical recordings",
        "non-musical audio recordings, except audio books",
        "admissions to live performing arts performances",
        "admissions to cultural institutions",
        "traveling exhibits",
        "table wagering games",
        "lotteries",
        "contract live sporting events",
        "outright sale of rights to intellectual property works protected by copyright",
    ],
    "72": ["accommodation", "food services", "food", "restaurant"],
    "81": ["other", "services", "non profit", "shelters", "wedding chapel", "hoa", "pet services"],
    "92": ["public", "administration", "government", "petroleum-free liquid biofuels"],
}


def boost_keywords(text: str, code: Any) -> str:
    """Boost domain keywords when NAICS/NAPCS code matches a table entry.

    Repeats any known keyword present in ``text`` if its sector ``code`` maps
    to a list in ``keyword_table``.
    """
    if pd.isna(code):
        return text

    # Convert code to string to avoid TypeError
    code_str = str(code)

    # Extract integer part of the code from the string
    # TODO - add global path function
    code_match = re.search(r"\d+", code_str)
    if code_match is None:
        return text

    sector = code_match.group()
    if sector in keyword_table:
        for keyword in keyword_table[sector]:
            if keyword.lower() in text:
                text += (" " + keyword.lower()) * 5
    return text


# Function to preprocess text
def preprocess_text(text: str) -> str:
    """Lowercase and normalize common patterns and punctuation."""
    text = text.lower()
    # TODO - add global path function
    text = re.sub(r"\bexcept\b.*", "", text)
    # TODO - add global path function
    text = re.sub(r"e\.g\.", "", text)
    # TODO - add global path function
    text = re.sub(r"[()\,\\/#!*&_=+\[\]{}|-]", "", text)
    # TODO - add global path function
    text = re.sub(r"\|", "", text)
    return text


# Function to preprocess NAICS and NAPCS codes
def preprocess_code(code: Any) -> str:
    """Return the first two digits of a code as a sector string."""
    return str(code)[:2]


# Function to compute average similarity
def compute_avg_similarity(matrix: Any) -> Any:
    """Compute row-wise average pairwise cosine similarity for a matrix."""
    cosine_similarities = cosine_similarity(matrix)
    avg_similarities = (cosine_similarities.sum(axis=1) - 1) / (cosine_similarities.shape[1] - 1)
    return avg_similarities


# Function to compute similarities within a single system
def compute_similarities(
    df: pd.DataFrame, use_all_columns: bool, code: str | None = None
) -> pd.DataFrame:
    """Compute TF–IDF similarities for either all columns or the 'item' column.

    Returns the original DataFrame with additional similarity columns.
    """
    df = df.copy()
    tfidf_vectorizer = TfidfVectorizer()

    if use_all_columns:
        df["all_text"] = df.apply(lambda row: " ".join(row.astype(str)), axis=1)
        df["all_text"] = df["all_text"].apply(preprocess_text)
        df["all_text"] = df.apply(lambda row: boost_keywords(row["all_text"], row["code"]), axis=1)
        text_matrix = tfidf_vectorizer.fit_transform(df["all_text"])
        df["Average similarity"] = compute_avg_similarity(text_matrix)
        del text_matrix  # Free up memory
    else:
        df["item"] = df["item"].apply(preprocess_text)
        df["item"] = df.apply(lambda row: boost_keywords(row["item"], row["code"]), axis=1)
        item_matrix = tfidf_vectorizer.fit_transform(df["item"])
        df["Average item similarity"] = compute_avg_similarity(item_matrix)
        del item_matrix  # Free up memory

    return df


# Load all tables
try:
    all_idx_df = pd.read_excel("your_file.xlsx", sheet_name="all_idx")
    main_df = pd.read_excel("your_file.xlsx", sheet_name="main")
    naics_df = pd.read_excel("your_file.xlsx", sheet_name="naics")
    sic_df = pd.read_excel("your_file.xlsx", sheet_name="sic")
    napcs_df = pd.read_excel("your_file.xlsx", sheet_name="napcs")
except Exception as e:
    print(f"Error while reading the file: {str(e)}")
    raise

# Preprocess codes
naics_df["code"] = naics_df["code"].apply(preprocess_code)
napcs_df["code"] = napcs_df["code"].apply(preprocess_code)

# Compute similarities within each system
all_idx_df = compute_similarities(all_idx_df, use_all_columns=True)
main_df = compute_similarities(main_df, use_all_columns=False)
naics_df = compute_similarities(naics_df, use_all_columns=True)
sic_df = compute_similarities(sic_df, use_all_columns=True)
napcs_df = compute_similarities(napcs_df, use_all_columns=True)

# Save the DataFrames to separate sheets
with pd.ExcelWriter("output_with_similarities.xlsx") as writer:
    all_idx_df.to_excel(writer, sheet_name="all_idx", index=False)
    main_df.to_excel(writer, sheet_name="main", index=False)
    naics_df.to_excel(writer, sheet_name="naics", index=False)
    sic_df.to_excel(writer, sheet_name="sic", index=False)
    napcs_df.to_excel(writer, sheet_name="napcs", index=False)
