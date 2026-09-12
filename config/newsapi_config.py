"""
NewsAPI configuration and budget management.

Free tier: 100 requests/day.
Budget is split between scheduled calls and on-demand reserves.
"""

# Categories to fetch from NewsAPI /v2/top-headlines
NEWSAPI_CATEGORIES = [
    "general",
    "technology",
    "business",
    "science",
    "health",
    "sports",
    "entertainment",
]

# Keywords for /v2/everything searches
NEWSAPI_KEYWORDS = [
    "artificial intelligence",
    "cryptocurrency bitcoin",
    "climate change",
    "space NASA",
    "elections",
    "cybersecurity",
]

# Schedule: when to run NewsAPI calls (hours in UTC)
# Morning (03:00 UTC = 08:00 PKT)
# Afternoon (09:00 UTC = 14:00 PKT)
# Evening (15:00 UTC = 20:00 PKT)
# Night (21:00 UTC = 02:00 PKT)
NEWSAPI_SCHEDULE_HOURS = [3, 9, 15, 21]

# How many articles per request
NEWSAPI_PAGE_SIZE = 20

# Base URL
NEWSAPI_BASE_URL = "https://newsapi.org/v2"

# Source quality mapping for NewsAPI sources
# NewsAPI includes source name — map known ones to quality scores
NEWSAPI_SOURCE_QUALITY = {
    "reuters": 10,
    "associated-press": 10,
    "bbc-news": 10,
    "the-wall-street-journal": 9,
    "the-washington-post": 9,
    "the-new-york-times": 9,
    "bloomberg": 9,
    "cnn": 8,
    "al-jazeera-english": 9,
    "the-verge": 8,
    "techcrunch": 8,
    "ars-technica": 9,
    "wired": 9,
    "engadget": 7,
    "espn": 9,
    "bbc-sport": 10,
    "google-news": 7,
    "default": 6,  # Unknown sources get quality 6
}
