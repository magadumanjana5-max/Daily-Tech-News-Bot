# Daily Global Tech News Scheduler

A beginner-friendly Python project that fetches technology news, stores articles in MongoDB, creates a daily briefing, and exposes the stored data through a REST API.

## Project objectives

- Collect technology news from a NewsAPI-compatible source.
- Categorize articles using editable keyword rules.
- Avoid storing the same article URL more than once.
- Score and select useful stories for a daily briefing.
- Save one briefing per date.
- Provide REST endpoints for latest news, category filtering, search, briefings, and health.
- Run the collection and briefing workflow every day at a configurable local time.

The briefing is a practical learning-project summary. Its category-based “why it matters,” learning, and career notes are simple templates, not independently verified analysis. Keyword classification and ranking can miss context.

## Technologies

- Python 3.10 or newer
- FastAPI and Uvicorn
- MongoDB and PyMongo
- Requests
- APScheduler
- `python-dotenv`
- VS Code and Postman

## Project structure

```text
daily-tech-news/
├── .env                  # Private local settings; never commit
├── .env.example          # Safe settings template
├── .gitignore            # Excludes secrets, virtual environment, and caches
├── .venv/                # Local Python virtual environment; generated
├── README.md             # Setup, data flow, and API guide
├── requirements.txt      # Python dependencies
├── config.py             # Reads environment settings and checks schedule values
├── models.py             # Category keywords and article categorization
├── database.py           # MongoDB connection, indexes, and save functions
├── news_service.py       # Fetches, validates, and normalizes provider JSON
├── briefing_service.py   # Scores articles and creates/formats briefings
├── scheduler.py          # Daily workflow and APScheduler setup
└── main.py               # FastAPI endpoints and application startup/shutdown
```

## Installation on Windows

Open the project folder in VS Code, then create and activate a virtual environment in PowerShell:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell does not allow activation, use the VS Code Command Prompt terminal:

```cmd
.venv\Scripts\activate.bat
```

In VS Code, choose **Python: Select Interpreter** and select the interpreter inside `.venv`.

## MongoDB setup

Use either a local MongoDB Community Server or a MongoDB Atlas cluster.

1. Start the local MongoDB server, or create an Atlas cluster and database user.
2. For Atlas, allow your development machine’s IP address in the project’s network access settings.
3. Copy the connection URI. Keep any username and password private. If credentials contain reserved URI characters, URL-encode them.
4. The application uses the `tech_news` database by default. MongoDB collections and indexes are prepared when the app connects.
5. Open MongoDB Compass and connect with the same URI. After the first successful write, inspect `tech_news` → `news` and `tech_news` → `daily_briefings`.

The application creates these unique indexes:

- `news.url` — prevents a URL from being stored more than once.
- `daily_briefings.briefing_date` — allows only one briefing document per date.

If an existing database already contains duplicate values, MongoDB may reject creation of the corresponding unique index. Remove or resolve those duplicate documents before starting the application.

## Environment variables and API key

Create a local `.env` file from the safe template:

```powershell
Copy-Item .env.example .env
```

Edit `.env` locally. Do not paste its real values into chat, screenshots, or GitHub. The `.gitignore` excludes `.env` and `.venv/`; `.env.example` contains placeholders and is safe to share.

| Variable | Purpose | Default |
| --- | --- | --- |
| `MONGODB_URI` | MongoDB connection URI | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `tech_news` |
| `NEWS_API_KEY` | API credential from your news provider | Required for fetching |
| `NEWS_API_BASE_URL` | NewsAPI-compatible endpoint | `https://newsapi.org/v2/everything` |
| `NEWS_QUERY` | Search expression sent to the provider | Technology, AI, quantum, and cybersecurity terms |
| `NEWS_SCHEDULE_HOUR` | Daily schedule hour, local machine time (`0`–`23`) | `6` |
| `NEWS_SCHEDULE_MINUTE` | Daily schedule minute (`0`–`59`) | `0` |

The project sends the key in the `X-Api-Key` HTTPS request header. It does not put the key in the request URL or print it. Check your provider’s current API documentation, limits, and terms before use; this project expects a NewsAPI-compatible response with an `articles` list.

## Run the application

With MongoDB running and `.env` configured, start the API and scheduler:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload
```

The scheduler runs the daily job at the configured local time while this process remains running. It does not run the job immediately at startup. For a one-time manual collection and briefing run, open a second terminal in the project folder and run:

```powershell
.\.venv\Scripts\python.exe -c "from scheduler import run_daily_news_job; print(run_daily_news_job())"
```

The job performs these steps:

1. Connects to MongoDB and ensures unique indexes exist.
2. Fetches and normalizes news-provider JSON.
3. Categorizes each valid article.
4. Inserts new article URLs and counts duplicate URLs.
5. Scores fetched articles and selects up to one article for each briefing section.
6. Saves or refreshes today’s briefing.
7. Prints the formatted briefing in the terminal.

If a step fails, the job logs the failure, propagates the exception, and closes its MongoDB client. The scheduler process remains active for future runs.

## How the code fits together

```text
.env
  └── config.py
       ├── database.py ─────────────── MongoDB connection and persistence
       ├── news_service.py ─────────── HTTPS request and article normalization
       │    └── models.py ──────────── keyword categorization
       ├── briefing_service.py ──────── scoring, section selection, formatting
       └── scheduler.py ────────────── daily fetch → save → brief workflow
                                            │
main.py (FastAPI startup) ──────────────────┴── REST API reads MongoDB
```

The API reads stored documents. It does not fetch fresh news for every request. `/health` checks MongoDB connectivity, and the scheduler starts with the FastAPI application.

## MongoDB collection structure

### `tech_news.news`

Example document (MongoDB also adds `_id` automatically):

```json
{
  "title": "Example technology headline",
  "description": "A short description from the news source.",
  "source": "Example News",
  "author": "Reporter Name",
  "url": "https://example.com/story",
  "category": "AI",
  "published_at": "2026-10-18T06:00:00Z",
  "collected_at": "2026-10-18T06:15:00Z"
}
```

`published_at` can be `null` when the provider does not return a usable date. PyMongo stores Python datetimes as BSON dates; the JSON above shows an ISO-formatted representation.

### `tech_news.daily_briefings`

Documents include `briefing_date`, `generated_at`, `created_at`, `total_news`, per-category counts, selected `top_news`, `learning_topic`, and `career_opportunity`. Selected stories include their section, title, summary, source, URL, category, score, and a short category-based “why it matters” note.

## REST API documentation

Once the application is running, open the interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

You can also use Postman. All endpoints return JSON. List endpoints return an object with a `count` and an array.

| Method and path | Description |
| --- | --- |
| `GET /health` | Check app and MongoDB availability. Returns `200` when connected or `503` when unavailable. |
| `GET /news?limit=50` | Latest stored articles, sorted by publication time. `limit` is from 1 to 100. |
| `GET /news/search?keyword=python` | Case-insensitive literal search across title, description, and category. |
| `GET /news/category/AI` | Filter by a supported category. Invalid categories return `400`. |
| `GET /news/{id}` | Fetch one article by MongoDB ObjectId. Invalid IDs return `400`; missing articles return `404`. |
| `GET /briefings?limit=30` | Previous briefings, newest date first. `limit` is from 1 to 100. |
| `GET /briefings/{date}` | Fetch a briefing using `YYYY-MM-DD`. Invalid dates return `400`; missing briefings return `404`. |

The search route is defined before the article-ID route so `/news/search` is treated as search rather than an ID.

### Sample Postman requests

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/news?limit=10
GET http://127.0.0.1:8000/news/search?keyword=python
GET http://127.0.0.1:8000/news/category/Quantum%20Computing
GET http://127.0.0.1:8000/news/652f1a000000000000000001
GET http://127.0.0.1:8000/briefings
GET http://127.0.0.1:8000/briefings/2026-10-18
```

### Example responses

`GET /health`:

```json
{
  "status": "ok",
  "database": "connected"
}
```

`GET /news?limit=1`:

```json
{
  "count": 1,
  "news": [
    {
      "_id": "652f1a000000000000000001",
      "title": "Example technology headline",
      "description": "A short description from the news source.",
      "source": "Example News",
      "author": "Reporter Name",
      "url": "https://example.com/story",
      "category": "AI",
      "published_at": "2026-10-18T06:00:00",
      "collected_at": "2026-10-18T06:15:00"
    }
  ]
}
```

An unavailable database returns an HTTP `503` with a brief message, not MongoDB credentials or internal exception details. A valid request with no matching list results returns a `count` of `0` and an empty array.

## Scoring and briefing selection

The simple score combines:

- **Category priority:** Agentic AI `+6`; AI, Quantum Computing, and Cybersecurity `+5`; Cloud `+4`; Developer Tools, Programming, Startups, and Technology Companies `+3`; Other Technology `+1`.
- **Importance wording:** `+2` if at least one configured word (such as “launch,” “breakthrough,” “breach,” or “funding”) appears in the title or description.
- **Recency:** `+3` within one day, `+2` within three days, `+1` within seven days.

The highest-scoring eligible story is chosen for each mapped section. URL duplicates are removed; similar stories with different URLs are not detected. “Why it matters,” learning, and career suggestions come from category templates and should be treated as learning prompts, not claims of expert analysis.

## Testing and demonstration

1. Start MongoDB, then launch FastAPI and the scheduler.
2. Run one manual job to avoid waiting until the configured schedule.
3. Inspect `tech_news.news` and `tech_news.daily_briefings` in MongoDB Compass.
4. Use Postman or `/docs` to check health, latest news, search, categories, and briefings.
5. Review the terminal briefing and configured scheduler time.

Mocked checks for category selection, news response normalization/error cases, duplicate article insertion, briefing scoring/formatting, scheduler setup, and workflow ordering have been run during development. A live news provider request and live MongoDB insert depend on your own API key and database; verify those in your local environment.

## Security reminders

- Never commit `.env`, credentials, API keys, or MongoDB passwords.
- Keep HTTPS enabled for the provider URL.
- Do not expose provider keys in Postman URLs or screenshots.
- The app is a learning project; add production-grade authentication and deployment safeguards before exposing it publicly.
