import os

from dotenv import load_dotenv


load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "tech_news")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY") or os.getenv("NEWS_API_KEY")
GNEWS_API_BASE_URL = os.getenv(
    "GNEWS_API_BASE_URL",
    "https://gnews.io/api/v4/search",
)
NEWS_QUERY = os.getenv(
    "NEWS_QUERY",
    "technology OR artificial intelligence OR quantum computing OR cybersecurity",
)


