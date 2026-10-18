import logging
from datetime import date, datetime, timezone
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler
from pymongo.mongo_client import MongoClient

from briefing_service import format_briefing, generate_daily_briefing
from database import connect_database, save_daily_briefing, save_news_articles
from news_service import NewsFetchError, fetch_news


logger = logging.getLogger(__name__)

SCHEDULE_INTERVALS = {
    "1m": {"label": "Every minute", "seconds": 60},
    "5m": {"label": "Every 5 minutes", "seconds": 5 * 60},
    "1h": {"label": "Every hour", "seconds": 60 * 60},
    "1d": {"label": "Every day", "seconds": 24 * 60 * 60},
}
DEFAULT_SCHEDULE_INTERVAL = "1d"
NEWS_JOB_ID = "scheduled_tech_news"
_job_status_lock = Lock()
_job_status: dict[str, object] = {
    "status": "waiting",
    "started_at": None,
    "finished_at": None,
    "inserted": 0,
    "duplicates": 0,
    "error": None,
}


def get_news_job_status() -> dict[str, object]:
    with _job_status_lock:
        return dict(_job_status)


def _update_news_job_status(**updates: object) -> None:
    with _job_status_lock:
        _job_status.update(updates)


def run_daily_news_job() -> dict[str, int]:
    """Fetch news, save new articles, and create today's briefing."""
    client: MongoClient | None = None
    started_at = datetime.now(timezone.utc).isoformat()
    _update_news_job_status(
        status="running",
        started_at=started_at,
        finished_at=None,
        error=None,
    )

    try:
        client, database = connect_database()
        articles = fetch_news()
        save_counts = save_news_articles(database, articles)

        briefing = generate_daily_briefing(articles, briefing_day=date.today())
        save_daily_briefing(database, briefing)
        print(format_briefing(briefing))

        logger.info(
            "Scheduled news job completed: fetched=%s inserted=%s duplicates=%s",
            len(articles),
            save_counts["inserted"],
            save_counts["duplicates"],
        )
        _update_news_job_status(
            status="success",
            finished_at=datetime.now(timezone.utc).isoformat(),
            inserted=save_counts["inserted"],
            duplicates=save_counts["duplicates"],
            error=None,
        )
        return save_counts
    except Exception as error:
        _update_news_job_status(
            status="failed",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=(
                str(error)
                if isinstance(error, NewsFetchError)
                else "Scheduled job failed. Check the server log for details."
            ),
        )
        logger.exception("Scheduled news job failed.")
        raise
    finally:
        if client is not None:
            client.close()


def start_scheduler(
    interval: str = DEFAULT_SCHEDULE_INTERVAL,
) -> BackgroundScheduler:
    """Start the news job using a supported recurring interval."""
    if interval not in SCHEDULE_INTERVALS:
        raise ValueError(f"Unsupported news schedule interval: {interval}")

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_daily_news_job,
        trigger="interval",
        seconds=SCHEDULE_INTERVALS[interval]["seconds"],
        id=NEWS_JOB_ID,
        replace_existing=True,
    )
    scheduler.start()

    logger.info("News scheduler started: %s.", SCHEDULE_INTERVALS[interval]["label"])
    return scheduler


def set_scheduler_interval(
    scheduler: BackgroundScheduler,
    interval: str,
    run_immediately: bool = False,
) -> None:
    """Change the recurring news interval and optionally queue a refresh now."""
    if interval not in SCHEDULE_INTERVALS:
        raise ValueError(f"Unsupported news schedule interval: {interval}")

    scheduler.reschedule_job(
        NEWS_JOB_ID,
        trigger="interval",
        seconds=SCHEDULE_INTERVALS[interval]["seconds"],
    )
    if run_immediately:
        scheduler.modify_job(
            NEWS_JOB_ID,
            next_run_time=datetime.now(timezone.utc),
        )

    logger.info("News scheduler interval changed to %s.", SCHEDULE_INTERVALS[interval]["label"])
