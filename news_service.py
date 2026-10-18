import logging
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from config import GNEWS_API_BASE_URL, GNEWS_API_KEY, NEWS_QUERY
from models import categorize_article


logger = logging.getLogger(__name__)


class NewsFetchError(Exception):
    """Raised when the news provider cannot return usable news data."""


def _parse_published_date(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_article(article: Any) -> Optional[dict[str, Any]]:
    if not isinstance(article, dict):
        return None

    title = article.get("title")
    url = article.get("url")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return None

    description = article.get("description")
    if not isinstance(description, str):
        description = ""

    source_data = article.get("source")
    source = source_data.get("name") if isinstance(source_data, dict) else None
    author = article.get("author")

    return {
        "title": title.strip(),
        "description": description.strip(),
        "source": source if isinstance(source, str) and source else "Unknown",
        "author": author if isinstance(author, str) and author else None,
        "published_at": _parse_published_date(article.get("publishedAt")),
        "url": url,
        "category": categorize_article(title, description),
        "collected_at": datetime.now(timezone.utc),
    }


def fetch_news() -> list[dict[str, Any]]:
    """Fetch and normalize articles from GNews."""
    if not GNEWS_API_KEY:
        raise NewsFetchError("GNEWS_API_KEY is not configured.")
    if not GNEWS_API_BASE_URL.startswith("https://"):
        raise NewsFetchError("GNEWS_API_BASE_URL must use HTTPS.")

    try:
        response = requests.get(
            GNEWS_API_BASE_URL,
            params={
                "q": NEWS_QUERY,
                "lang": "en",
                "sortby": "publishedAt",
                "max": 10,
                "apikey": GNEWS_API_KEY,
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.Timeout as error:
        raise NewsFetchError("The news provider request timed out.") from None
    except requests.ConnectionError as error:
        raise NewsFetchError("Could not reach the news provider.") from None
    except requests.HTTPError as error:
        provider_response = error.response
        status = provider_response.status_code if provider_response is not None else "unknown"
        if status == 403:
            try:
                provider_payload = provider_response.json() if provider_response else {}
            except ValueError:
                provider_payload = {}
            provider_detail = (
                provider_payload.get("errors")
                or provider_payload.get("message")
                or provider_payload.get("error")
            ) if isinstance(provider_payload, dict) else None
            if isinstance(provider_detail, (list, dict)):
                provider_detail = str(provider_detail)
            if isinstance(provider_detail, str):
                provider_detail = provider_detail.replace(GNEWS_API_KEY, "[redacted]")
            else:
                provider_detail = "No additional provider details were returned."
            raise NewsFetchError(
                f"GNews rejected the request (HTTP 403): {provider_detail} "
                "Check that the API key is active and belongs to your GNews account."
            ) from None
        raise NewsFetchError(f"The news provider returned HTTP status {status}.") from None
    except requests.RequestException as error:
        raise NewsFetchError("The news provider request failed.") from None

    try:
        payload = response.json()
    except ValueError as error:
        raise NewsFetchError("GNews returned invalid JSON.") from None

    if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
        raise NewsFetchError("The news provider response has an unexpected format.")

    articles = payload["articles"]
    if not articles:
        logger.info("The news provider returned no articles for the configured query.")
        return []

    normalized = [_normalize_article(article) for article in articles]
    valid_articles = [article for article in normalized if article is not None]
    skipped_count = len(articles) - len(valid_articles)
    if skipped_count:
        logger.warning("Skipped %s invalid article entries.", skipped_count)

    if not valid_articles:
        logger.warning("The news provider response contained no usable articles.")

    return valid_articles
