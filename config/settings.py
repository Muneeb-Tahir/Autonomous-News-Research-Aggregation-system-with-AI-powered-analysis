"""
Central settings for the News Intelligence Agent.

All configurable values in one place. Modify these to tune
collection frequency, scoring weights, thresholds, and behavior.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================
# API Keys (loaded from .env)
# =============================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# =============================================================
# Server
# =============================================================
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

# =============================================================
# Collection Timing
# =============================================================
COLLECTION_INTERVAL_MINUTES = 30        # RSS collection frequency
NEWSAPI_CATEGORY_INTERVAL_HOURS = 6     # NewsAPI category calls
NEWSAPI_KEYWORD_INTERVAL_HOURS = 8      # NewsAPI keyword calls
CLEANUP_INTERVAL_HOURS = 1              # Old article cleanup

# =============================================================
# Retention
# =============================================================
MAX_ARTICLES = 2000                     # Max articles in database
MAX_AGE_HOURS = 168                     # Delete articles older than 7 days

# =============================================================
# Scoring Weights (must sum to 1.0)
# =============================================================
WEIGHT_IMPORTANCE = 0.35
WEIGHT_RECENCY = 0.20
WEIGHT_CREDIBILITY = 0.20
WEIGHT_URGENCY = 0.10
WEIGHT_SOURCE_QUALITY = 0.10
WEIGHT_CATEGORY_BOOST = 0.05

# =============================================================
# Breaking News
# =============================================================
BREAKING_IMPORTANCE_THRESHOLD = 82      # Minimum importance to be breaking
BREAKING_URGENCY_THRESHOLD = 75         # Minimum urgency to be breaking
BREAKING_COOLDOWN_HOURS = 2             # Don't re-alert same story within this

# =============================================================
# Cache
# =============================================================
CACHE_TTL_SECONDS = 300                 # 5 minutes

# =============================================================
# Timezone
# =============================================================
USER_TIMEZONE = "Asia/Karachi"

# =============================================================
# Deduplication
# =============================================================
TITLE_SIMILARITY_THRESHOLD = 0.50       # 50% word overlap = duplicate
STORY_GROUP_SIMILARITY = 0.50           # 50% overlap = same story group

# =============================================================
# Language
# =============================================================
LANGUAGE_FILTER = "en"
ASCII_RATIO_THRESHOLD = 0.80            # Title must be 80%+ ASCII

# =============================================================
# NewsAPI Budget (100 requests/day)
# =============================================================
NEWSAPI_DAILY_LIMIT = 100
NEWSAPI_RESERVED_FOR_ONDEMAND = 59      # Reserved for user queries

# =============================================================
# Gemini
# =============================================================
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_TEMPERATURE = 0.1                # Low = factual
GEMINI_MAX_OUTPUT_TOKENS = 4096

# =============================================================
# Logging
# =============================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# =============================================================
# Category Configuration
# =============================================================
ALL_CATEGORIES = [
    "WORLD", "POLITICS", "BUSINESS", "FINANCE", "TECHNOLOGY",
    "AI", "SCIENCE", "HEALTH", "CLIMATE", "ENVIRONMENT",
    "SPORTS", "GAMING", "ENTERTAINMENT", "MOVIES", "TV",
    "MUSIC", "SPACE", "EDUCATION", "CYBERSECURITY", "STARTUPS",
    "CRYPTO", "AUTOMOTIVE", "TRAVEL", "LIFESTYLE", "GENERAL", "OTHER"
]

# Category base weights for importance scoring
CATEGORY_WEIGHTS = {
    "WORLD": 70,
    "POLITICS": 65,
    "BUSINESS": 60,
    "FINANCE": 60,
    "TECHNOLOGY": 55,
    "AI": 55,
    "SCIENCE": 55,
    "HEALTH": 60,
    "CLIMATE": 55,
    "ENVIRONMENT": 50,
    "SPORTS": 40,
    "GAMING": 30,
    "ENTERTAINMENT": 35,
    "MOVIES": 30,
    "TV": 30,
    "MUSIC": 25,
    "SPACE": 50,
    "EDUCATION": 40,
    "CYBERSECURITY": 50,
    "STARTUPS": 40,
    "CRYPTO": 40,
    "AUTOMOTIVE": 35,
    "TRAVEL": 25,
    "LIFESTYLE": 25,
    "GENERAL": 50,
    "OTHER": 40,
}

# Category aliases for user queries
CATEGORY_ALIASES = {
    "ai": "AI",
    "tech": "TECHNOLOGY",
    "technology": "TECHNOLOGY",
    "biz": "BUSINESS",
    "business": "BUSINESS",
    "world": "WORLD",
    "politics": "POLITICS",
    "sports": "SPORTS",
    "sport": "SPORTS",
    "crypto": "CRYPTO",
    "bitcoin": "CRYPTO",
    "science": "SCIENCE",
    "health": "HEALTH",
    "space": "SPACE",
    "gaming": "GAMING",
    "games": "GAMING",
    "entertainment": "ENTERTAINMENT",
    "movies": "MOVIES",
    "movie": "MOVIES",
    "tv": "TV",
    "music": "MUSIC",
    "cyber": "CYBERSECURITY",
    "security": "CYBERSECURITY",
    "finance": "FINANCE",
    "markets": "FINANCE",
    "stocks": "FINANCE",
    "climate": "CLIMATE",
    "environment": "ENVIRONMENT",
    "education": "EDUCATION",
    "startups": "STARTUPS",
    "startup": "STARTUPS",
    "automotive": "AUTOMOTIVE",
    "cars": "AUTOMOTIVE",
    "travel": "TRAVEL",
    "lifestyle": "LIFESTYLE",
}

# Breaking news keywords (boost urgency when found in title)
BREAKING_KEYWORDS = [
    "breaking", "earthquake", "explosion", "shooting", "crash",
    "killed", "dead", "dies", "war", "attack", "emergency",
    "tsunami", "hurricane", "tornado", "assassination", "coup",
    "invasion", "hostage", "bombing", "collapse", "outbreak",
    "pandemic", "evacuation", "martial law", "ceasefire",
    "nuclear", "missile", "strikes", "floods", "wildfire",
]
