import logging
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from pymongo.database import Database
from pymongo.errors import PyMongoError

from database import connect_database
from models import NEWS_CATEGORIES
from scheduler import (
    DEFAULT_SCHEDULE_INTERVAL,
    SCHEDULE_INTERVALS,
    NEWS_JOB_ID,
    get_news_job_status,
    set_scheduler_interval,
    start_scheduler,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScheduleUpdate(BaseModel):
    interval: Literal["1m", "5m", "1h", "1d"]


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.mongo_client = None
    application.state.database = None
    application.state.scheduler = None
    application.state.news_interval = DEFAULT_SCHEDULE_INTERVAL

    try:
        client, database = connect_database()
    except (ConnectionError, RuntimeError):
        logger.exception("MongoDB startup connection failed.")
    else:
        application.state.mongo_client = client
        application.state.database = database

        try:
            settings = database["application_settings"].find_one(
                {"_id": "news_schedule"}
            )
        except PyMongoError:
            logger.exception("Could not read the saved news schedule; using daily default.")
        else:
            saved_interval = settings.get("interval") if settings else None
            if saved_interval in SCHEDULE_INTERVALS:
                application.state.news_interval = saved_interval

    application.state.scheduler = start_scheduler(application.state.news_interval)
    yield

    application.state.scheduler.shutdown(wait=False)
    if application.state.mongo_client is not None:
        application.state.mongo_client.close()


app = FastAPI(
    title="Daily Global Tech News Scheduler",
    description="A beginner-friendly technology news collection and briefing API.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/ui", include_in_schema=False)
def api_test_ui():
    return FileResponse(Path(__file__).parent / "static" / "api_tester.html")


def _schedule_status(request: Request) -> dict[str, Any]:
    interval = request.app.state.news_interval
    job = request.app.state.scheduler.get_job(NEWS_JOB_ID)
    next_run_at = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        "interval": interval,
        "label": SCHEDULE_INTERVALS[interval]["label"],
        "next_run_at": next_run_at,
        "last_job": get_news_job_status(),
        "options": [
            {"value": key, **details}
            for key, details in SCHEDULE_INTERVALS.items()
        ],
    }


@app.get("/schedule")
def get_schedule(request: Request):
    return _schedule_status(request)


@app.post("/schedule")
def update_schedule(settings: ScheduleUpdate, request: Request):
    database = _get_database(request)
    try:
        database["application_settings"].update_one(
            {"_id": "news_schedule"},
            {
                "$set": {
                    "interval": settings.interval,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except PyMongoError as error:
        _raise_database_error(error)

    set_scheduler_interval(
        request.app.state.scheduler,
        settings.interval,
        run_immediately=True,
    )
    request.app.state.news_interval = settings.interval
    return _schedule_status(request)


def _get_database(request: Request) -> Database:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is unavailable. Check the database connection.",
        )
    return database


def _raise_database_error(error: PyMongoError) -> None:
    logger.exception("A MongoDB request failed.")
    raise HTTPException(
        status_code=503,
        detail="MongoDB is temporarily unavailable.",
    ) from error


def _serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    document = dict(document)
    if "_id" in document:
        document["_id"] = str(document["_id"])
    return jsonable_encoder(document)


@app.get("/health")
def health(request: Request):
    client = getattr(request.app.state, "mongo_client", None)
    if client is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "disconnected"},
        )

    try:
        client.admin.command("ping")
    except PyMongoError:
        logger.exception("Health check could not reach MongoDB.")
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "disconnected"},
        )

    return {"status": "ok", "database": "connected"}


@app.get("/news")
def get_latest_news(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
):
    database = _get_database(request)
    try:
        articles = list(
            database["news"]
            .find()
            .sort("published_at", -1)
            .limit(limit)
        )
    except PyMongoError as error:
        _raise_database_error(error)

    serialized = [_serialize_document(article) for article in articles]
    return {"count": len(serialized), "news": serialized}


@app.get("/news/search")
def search_news(
    request: Request,
    keyword: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
):
    keyword = keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword cannot be empty.")

    database = _get_database(request)
    query = {
        "$or": [
            {"title": {"$regex": re.escape(keyword), "$options": "i"}},
            {"description": {"$regex": re.escape(keyword), "$options": "i"}},
            {"category": {"$regex": re.escape(keyword), "$options": "i"}},
        ]
    }

    try:
        articles = list(
            database["news"]
            .find(query)
            .sort("published_at", -1)
            .limit(limit)
        )
    except PyMongoError as error:
        _raise_database_error(error)

    serialized = [_serialize_document(article) for article in articles]
    return {"count": len(serialized), "news": serialized}


@app.get("/news/category/{category}")
def get_news_by_category(category: str, request: Request):
    category_lookup = {name.casefold(): name for name in NEWS_CATEGORIES}
    selected_category = category_lookup.get(category.casefold())
    if selected_category is None:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid category.",
                "valid_categories": list(NEWS_CATEGORIES),
            },
        )

    database = _get_database(request)
    try:
        articles = list(
            database["news"]
            .find({"category": selected_category})
            .sort("published_at", -1)
        )
    except PyMongoError as error:
        _raise_database_error(error)

    serialized = [_serialize_document(article) for article in articles]
    return {"count": len(serialized), "news": serialized}


@app.get("/news/{article_id}")
def get_news_article(article_id: str, request: Request):
    if not ObjectId.is_valid(article_id):
        raise HTTPException(status_code=400, detail="Article ID is invalid.")

    database = _get_database(request)
    try:
        article = database["news"].find_one({"_id": ObjectId(article_id)})
    except PyMongoError as error:
        _raise_database_error(error)

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return _serialize_document(article)


@app.get("/briefings")
def get_briefings(
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
):
    database = _get_database(request)
    try:
        briefings = list(
            database["daily_briefings"]
            .find()
            .sort("briefing_date", -1)
            .limit(limit)
        )
    except PyMongoError as error:
        _raise_database_error(error)

    serialized = [_serialize_document(briefing) for briefing in briefings]
    return {"count": len(serialized), "briefings": serialized}


@app.get("/briefings/{briefing_date}")
def get_briefing(briefing_date: str, request: Request):
    try:
        parsed_date = date.fromisoformat(briefing_date)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Date must use YYYY-MM-DD format.",
        ) from error

    if parsed_date.isoformat() != briefing_date:
        raise HTTPException(
            status_code=400,
            detail="Date must use YYYY-MM-DD format.",
        )

    database = _get_database(request)
    try:
        briefing = database["daily_briefings"].find_one(
            {"briefing_date": briefing_date}
        )
    except PyMongoError as error:
        _raise_database_error(error)

    if briefing is None:
        raise HTTPException(status_code=404, detail="Briefing not found.")
    return _serialize_document(briefing)
