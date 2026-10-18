# Daily Tech News Bot: Project Flow

## 1. Complete Project Flow

The application has two related paths: a background collection path that fetches and stores news, and a request path that reads saved data for the UI, REST API, or Postman.

### Background collection path

1. `config.py` loads settings from `.env`, including MongoDB connection details, the GNews API key, the news query, and the GNews endpoint.
2. When FastAPI starts, the lifespan handler in `main.py` connects to MongoDB, prepares indexes, restores the saved schedule interval, and starts the APScheduler background scheduler.
3. At each scheduled run, APScheduler calls `run_daily_news_job()` in `scheduler.py`.
4. `run_daily_news_job()` calls `fetch_news()` in `news_service.py`.
5. `fetch_news()` sends an HTTPS request to GNews. It validates the response, normalizes article fields, parses publication dates, and assigns each article a category using the keyword rules in `models.py`.
6. The job saves the normalized articles to MongoDB. It then scores the fetched articles and creates a daily briefing with `briefing_service.py`, saving or updating that date's briefing.
7. The scheduler records the latest job status. The UI reads that status and reloads the saved news after a successful run.

### Read and display path

The UI at `/ui`, the REST endpoints in `main.py`, and Postman all make HTTP requests to FastAPI. FastAPI reads the saved documents from MongoDB and returns JSON. It does not call GNews every time someone opens the news endpoint. This separation keeps browser/API reads quick and makes collection happen on the selected schedule.

The UI polls `/schedule` for job status and next-run information. After it sees a completed successful run, it requests `/news` again and renders the updated articles. If a fetch fails, the UI shows the failure status; it cannot show newly fetched stories until a later run succeeds.

To start the application on Windows, run this from the project folder:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Keep the server running for scheduled jobs. The UI is at `http://127.0.0.1:8000/ui`; interactive API docs are at `http://127.0.0.1:8000/docs`.

## 2. Why Use a Scheduler, and How Does It Call Python?

A scheduler runs collection without requiring a person to click a button or run a command each time. It keeps the news database and briefing up to date while the application is running.

This project uses APScheduler's `BackgroundScheduler`. In `scheduler.py`, `start_scheduler()` registers the function as a job:

```python
scheduler.add_job(
	 run_daily_news_job,
	 trigger="interval",
	 seconds=SCHEDULE_INTERVALS[interval]["seconds"],
	 id=NEWS_JOB_ID,
	 replace_existing=True,
)
```

The scheduler receives the function itself, `run_daily_news_job`, rather than calling it immediately during registration. APScheduler runs that function on a background thread when the interval expires. The supported intervals are 60 seconds, 5 minutes, 1 hour, and 24 hours.

When a user changes the schedule in the UI, the browser sends `POST /schedule`. The API saves the selected interval in MongoDB, reschedules the APScheduler job, and sets its next run to now. That causes one immediate fetch to test the new setting; subsequent fetches use the chosen interval. On application startup, the saved interval is loaded and the recurring job is registered again.

The UI's four-second polling is only for observing status and refreshing what is displayed. It does not fetch news from GNews every four seconds; GNews requests are made by the scheduled Python job.

## 3. What If the Server Is Stopped Before a Scheduled Run?

The scheduler is an in-process `BackgroundScheduler`. It exists only while the Python application is running. If the server is stopped at 6 AM and a run was expected at 7 AM, that run does not happen at 7 AM because there is no running scheduler. This project does not queue missed runs for later.

When the application starts again, it restores the selected interval from MongoDB and starts a new in-memory schedule. The next run is based on that new scheduler start time (or an immediate schedule change), not on the missed run time.

Also, the UI's “Every day” option currently means once every 24 hours after the scheduler starts or the interval is changed. It does **not** mean a fixed wall-clock time such as 7:00 AM. To require a fixed daily time and defined catch-up behavior after downtime, the scheduler would need a clock-based trigger such as APScheduler's `CronTrigger` plus an explicit misfire policy or a persistent job store.

## 4. How Are Duplicate News Articles Prevented in MongoDB?

`connect_database()` in `database.py` creates a unique index on the `url` field in the `news` collection:

```python
database["news"].create_index("url", unique=True)
```

The job attempts to insert each normalized article. If MongoDB already has the same URL, the unique index rejects the insert with `DuplicateKeyError`; `save_news_articles()` catches it and increments the duplicate count. Because the rule is enforced by MongoDB, it also protects against two jobs trying to insert the same URL at nearly the same time.

Deduplication is by exact URL, not by headline or story meaning. If a publisher supplies different URL variants for the same story, those variants may still be stored separately.

Briefings are separately protected by a unique index on `briefing_date`. Saving a briefing uses an upsert, so a later successful run updates that date's briefing instead of creating a second briefing document for the same day.

## 5. How News Travels from GNews to Python, MongoDB, REST API, and Postman

```text
GNews API
	| HTTPS JSON response
	v
news_service.fetch_news()
	| validate, normalize, parse date, categorize
	v
scheduler.run_daily_news_job()
	| insert articles and upsert briefing
	v
MongoDB: news and daily_briefings
	| read queries
	v
FastAPI REST endpoints
	| JSON over HTTP
	+---------------------> Browser UI
	+---------------------> Postman
```

1. **GNews to Python:** `news_service.py` sends a GET request to the GNews search endpoint with the query, language, sort order, article limit, and API key. GNews returns JSON containing an `articles` list. The API key belongs in `.env`; do not put it in source code or share it in logs/screenshots.
2. **Python processing:** The service checks that the response has the expected shape, skips entries without a usable title or HTTP(S) URL, converts GNews field names to the application's article fields, parses `publishedAt`, and assigns a category. `scheduler.py` passes those records to the persistence and briefing functions.
3. **Python to MongoDB:** `database.py` inserts articles into `tech_news.news` (unless their URL already exists) and upserts the daily briefing into `tech_news.daily_briefings`.
4. **MongoDB to REST API:** The FastAPI routes in `main.py` query MongoDB and serialize the documents as JSON. Examples include `GET /health`, `GET /news?limit=10`, `GET /news/search?keyword=python`, `GET /briefings`, and `GET /schedule`.
5. **REST API to UI or Postman:** The browser UI calls the same local FastAPI endpoints and renders their JSON results. In Postman, send a GET request to `http://127.0.0.1:8000/news?limit=10` to inspect stored stories, or `http://127.0.0.1:8000/schedule` to inspect the selected interval and job status. Postman is a client for testing the REST API; it does not communicate directly with MongoDB or GNews.

If GNews rejects the key or the request, the scheduled job is marked failed and no new articles are stored for that run. Existing MongoDB articles remain available through the UI and REST API.
