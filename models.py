import re


CATEGORY_KEYWORDS = {
    "Agentic AI": (
        "agentic ai",
        "ai agent",
        "autonomous agent",
        "ai agents",
    ),
    "Quantum Computing": (
        "quantum computing",
        "quantum computer",
        "qubit",
        "quantum",
    ),
    "AI": (
        "ai",
        "artificial intelligence",
        "machine learning",
        "generative ai",
        "large language model",
        "llm",
    ),
    "Cloud": (
        "cloud computing",
        "cloud service",
        "cloud platform",
        "aws",
        "azure",
        "google cloud",
    ),
    "Cybersecurity": (
        "cybersecurity",
        "cyber security",
        "ransomware",
        "data breach",
        "vulnerability",
        "security update",
    ),
    "Developer Tools": (
        "developer tool",
        "code editor",
        "visual studio code",
        "vs code",
        "ide ",
        "devops",
    ),
    "Programming": (
        "programming",
        "programming language",
        "python",
        "javascript",
        "open source",
        "software development",
    ),
    "Startups": (
        "startup",
        "start-up",
        "venture capital",
        "funding round",
        "raises funding",
    ),
    "Technology Companies": (
        "apple",
        "alphabet",
        "amazon",
        "microsoft",
        "meta",
        "nvidia",
        "intel",
        "samsung",
    ),
}

NEWS_CATEGORIES = tuple(CATEGORY_KEYWORDS) + ("Other Technology",)


def categorize_article(title: str, description: str = "") -> str:
    """Choose the first category with a keyword in the article text."""
    text = f" {title} {description} ".casefold()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword.casefold())}\b", text):
                return category

    return "Other Technology"
