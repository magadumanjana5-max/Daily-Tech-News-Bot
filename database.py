from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from config import MONGODB_DATABASE, MONGODB_URI


def connect_database() -> tuple[MongoClient, Database]:
    client: Optional[MongoClient] = None

    try:
        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
        )
        client.admin.command("ping")
    except PyMongoError as error:
        if client is not None:
            client.close()

        raise ConnectionError(
            "Could not connect to MongoDB. Check that MongoDB is running "
            "and MONGODB_URI is correct."
        ) from error

    database = client[MONGODB_DATABASE]

    try:
        database["news"].create_index("url", unique=True)
        database["daily_briefings"].create_index("briefing_date", unique=True)
    except PyMongoError as error:
        client.close()
        raise RuntimeError(
            "Could not prepare MongoDB collections and indexes. "
            "Check the database configuration and existing data."
        ) from error

    return client, database


def save_news_articles(
    database: Database,
    articles: list[dict[str, object]],
) -> dict[str, int]:
    """Insert new articles and count URLs already present in the collection."""
    inserted_count = 0
    duplicate_count = 0

    for article in articles:
        try:
            database["news"].insert_one(article)
            inserted_count += 1
        except DuplicateKeyError:
            duplicate_count += 1
        except PyMongoError as error:
            raise RuntimeError(
                "Could not save news articles to MongoDB."
            ) from error

    return {
        "inserted": inserted_count,
        "duplicates": duplicate_count,
    }


def save_daily_briefing(
    database: Database,
    briefing: dict[str, object],
) -> None:
    """Insert or refresh the briefing document for its date."""
    briefing_date = briefing.get("briefing_date")
    if not isinstance(briefing_date, str):
        raise ValueError(
            "Briefing must include a briefing_date in YYYY-MM-DD format."
        )

    document = dict(briefing)
    created_at = document.pop("created_at", None)

    try:
        database["daily_briefings"].update_one(
            {"briefing_date": briefing_date},
            {
                "$set": document,
                "$setOnInsert": {"created_at": created_at},
            },
            upsert=True,
        )
    except PyMongoError as error:
        raise RuntimeError("Could not save the daily briefing to MongoDB.") from error
