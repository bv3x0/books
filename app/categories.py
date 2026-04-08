"""
BISAC Subject Headings - Main Categories
https://www.bisg.org/BISAC-Subject-Codes-main
"""

BISAC_CATEGORIES = [
    "antiques & collectibles",
    "architecture",
    "art",
    "bibles",
    "biography & autobiography",
    "business & economics",
    "comics & graphic novels",
    "computers",
    "cooking",
    "crafts & hobbies",
    "design",
    "drama",
    "education",
    "family & relationships",
    "fiction",
    "games & activities",
    "gardening",
    "health & fitness",
    "history",
    "house & home",
    "humor",
    "juvenile fiction",
    "juvenile nonfiction",
    "language arts & disciplines",
    "language study",
    "law",
    "literary collections",
    "literary criticism",
    "mathematics",
    "medical",
    "music",
    "nature",
    "performing arts",
    "pets",
    "philosophy",
    "photography",
    "poetry",
    "political science",
    "psychology",
    "reference",
    "religion",
    "science",
    "self-help",
    "social science",
    "sports & recreation",
    "study aids",
    "technology & engineering",
    "transportation",
    "travel",
    "true crime",
    "young adult fiction",
    "young adult nonfiction",
]

# Create a set for O(1) lookup performance
_BISAC_CATEGORIES_SET = set(BISAC_CATEGORIES)


def get_categories_for_prompt() -> str:
    """Returns a formatted string of categories for use in LLM prompts."""
    return ", ".join(BISAC_CATEGORIES)


def validate_categories(categories: list[str]) -> list[str]:
    """
    Validates and normalizes a list of categories against BISAC standards.
    Returns only valid categories in lowercase.
    
    Args:
        categories: List of category strings to validate
        
    Returns:
        List of valid BISAC categories in lowercase
    """
    valid = []
    for cat in categories:
        if not cat:  # Skip empty strings
            continue
        cat_lower = cat.lower().strip()
        if cat_lower in _BISAC_CATEGORIES_SET:
            valid.append(cat_lower)
    return valid

