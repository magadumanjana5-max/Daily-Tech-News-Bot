from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from models import NEWS_CATEGORIES


CATEGORY_SCORES = {
    "Agentic AI": 6,
    "AI": 5,
    "Quantum Computing": 5,
    "Cybersecurity": 5,
    "Cloud": 4,
    "Developer Tools": 3,
    "Programming": 3,
    "Startups": 3,
    "Technology Companies": 3,
    "Other Technology": 1,
}

IMPORTANCE_KEYWORDS = (
    "launch",
    "announces",
    "breakthrough",
    "breach",
    "funding",
    "acquisition",
    "regulation",
)

BRIEFING_SECTIONS = (
    ("AI", ("AI",)),
    ("AGENTIC AI", ("Agentic AI",)),
    ("QUANTUM COMPUTING", ("Quantum Computing",)),
    ("CLOUD & SOFTWARE", ("Cloud", "Programming", "Developer Tools")),
    ("CYBERSECURITY", ("Cybersecurity",)),
    (
        "TECHNOLOGY BUSINESS",
        ("Startups", "Technology Companies"),
    ),
)

WHY_IT_MATTERS = {
    "AI": "AI changes can affect how people work, learn, and build software.",
    "Agentic AI": "Agent-based systems may automate multi-step digital tasks.",
    "Quantum Computing": "Quantum research may shape future computing capabilities.",
    "Cloud": "Cloud changes can affect the cost, reliability, and scale of software.",
    "Programming": "Programming updates can influence how developers build and maintain software.",
    "Developer Tools": "Developer tools affect the speed and quality of software work.",
    "Cybersecurity": "Security news can help organizations understand risks and protect systems.",
    "Startups": "Startup developments can reveal new products, business models, and investment trends.",
    "Technology Companies": "Major company decisions can influence products and the wider technology market.",
    "Other Technology": "This is a technology development worth keeping on the radar.",
}

LEARNING_TOPICS = {
    "AI": "Try building a small application that calls an AI model through an API.",
    "Agentic AI": "Learn how an AI agent plans steps and uses tools safely.",
    "Quantum Computing": "Learn the basic ideas of qubits and quantum gates.",
    "Cloud": "Practice deploying a simple web application to a cloud platform.",
    "Programming": "Study the programming language or open-source project in the headline.",
    "Developer Tools": "Practice using the developer tool or workflow mentioned in the news.",
    "Cybersecurity": "Learn a basic secure-coding practice related to the reported risk.",
    "Startups": "Study how a technology startup validates a product idea.",
    "Technology Companies": "Compare the company’s announcement with its earlier products.",
    "Other Technology": "Read about the core technology mentioned in the selected headline.",
}

CAREER_SKILLS = {
    "AI": "AI application development and machine learning fundamentals",
    "Agentic AI": "AI agent development, tool integration, and evaluation",
    "Quantum Computing": "Quantum information and scientific programming",
    "Cloud": "Cloud platforms, deployment, and reliability engineering",
    "Programming": "Programming and software development",
    "Developer Tools": "Developer productivity and DevOps practices",
    "Cybersecurity": "Security engineering and incident response",
    "Startups": "Product development and technology entrepreneurship",
    "Technology Companies": "Software, product, and business roles in technology companies",
    "Other Technology": "Technology research and problem-solving",
}


def score_article(article: dict[str, Any], now: datetime | None = None) -> int:
    """Score by topic priority, recency, and importance words."""
    score = CATEGORY_SCORES.get(article.get("category", "Other Technology"), 1)
    text = f"{article.get('title', '')} {article.get('description', '')}".casefold()

    if any(keyword in text for keyword in IMPORTANCE_KEYWORDS):
        score += 2

    published_at = article.get("published_at")
    if isinstance(published_at, datetime):
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        age = current_time - published_at
        if timedelta(0) <= age <= timedelta(days=1):
            score += 3
        elif timedelta(0) <= age <= timedelta(days=3):
            score += 2
        elif timedelta(0) <= age <= timedelta(days=7):
            score += 1

    return score


def _unique_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = []
    seen_urls = set()

    for article in articles:
        url = article.get("url")
        title = article.get("title")
        if not isinstance(url, str) or not isinstance(title, str) or not title.strip():
            continue
        if url in seen_urls:
            continue

        seen_urls.add(url)
        unique.append(article)

    return unique


def _article_order(article: dict[str, Any]) -> tuple[int, float]:
    published_at = article.get("published_at")
    if not isinstance(published_at, datetime):
        timestamp = 0.0
    else:
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        timestamp = published_at.timestamp()

    return score_article(article), timestamp


def generate_daily_briefing(
    articles: list[dict[str, Any]],
    briefing_day: date | None = None,
) -> dict[str, Any]:
    """Select the strongest article for each briefing section."""
    current_day = briefing_day or date.today()
    unique_articles = _unique_articles(articles)
    category_counts = Counter(
        article.get("category", "Other Technology")
        for article in unique_articles
    )
    categories = {category: category_counts.get(category, 0) for category in NEWS_CATEGORIES}

    ranked_articles = sorted(unique_articles, key=_article_order, reverse=True)
    top_news = []
    used_urls = set()

    for section_name, section_categories in BRIEFING_SECTIONS:
        for article in ranked_articles:
            if article.get("category") not in section_categories:
                continue
            if article["url"] in used_urls:
                continue

            category = article.get("category", "Other Technology")
            summary = article.get("description") or article["title"]
            top_news.append(
                {
                    "section": section_name,
                    "title": article["title"],
                    "summary": summary,
                    "why_it_matters": WHY_IT_MATTERS[category],
                    "source": article.get("source", "Unknown"),
                    "url": article["url"],
                    "category": category,
                    "score": score_article(article),
                }
            )
            used_urls.add(article["url"])
            break

    if top_news:
        first_category = top_news[0]["category"]
        learning_topic = LEARNING_TOPICS[first_category]
        career_opportunity = CAREER_SKILLS[first_category]
    else:
        learning_topic = "Choose one technology topic you are curious about and read its fundamentals."
        career_opportunity = "No clear career trend can be inferred because there were no matching articles."

    return {
        "briefing_date": current_day.isoformat(),
        "generated_at": datetime.now(timezone.utc),
        "total_news": len(unique_articles),
        "categories": categories,
        "top_news": top_news,
        "learning_topic": learning_topic,
        "career_opportunity": career_opportunity,
        "created_at": datetime.now(timezone.utc),
    }


def format_briefing(briefing: dict[str, Any]) -> str:
    """Render the briefing document as readable terminal text."""
    lines = [
        "DAILY GLOBAL TECH BRIEFING",
        f"Date: {briefing['briefing_date']}",
        f"Articles reviewed: {briefing['total_news']}",
        "",
    ]

    stories_by_section = {
        story["section"]: story for story in briefing["top_news"]
    }
    for number, (section_name, _) in enumerate(BRIEFING_SECTIONS, start=1):
        lines.append(f"{number}. {section_name}")
        story = stories_by_section.get(section_name)
        if story is None:
            lines.append("- No matching news today.")
        else:
            lines.extend(
                [
                    f"- {story['title']}",
                    f"  Summary: {story['summary']}",
                    f"  Why it matters: {story['why_it_matters']}",
                    f"  Source: {story['source']} ({story['url']})",
                ]
            )
        lines.append("")

    lines.extend(
        [
            "7. LEARNING OF THE DAY",
            f"- {briefing['learning_topic']}",
            "",
            "8. CAREER OPPORTUNITY",
            f"- Relevant skill: {briefing['career_opportunity']}",
        ]
    )
    return "\n".join(lines)
