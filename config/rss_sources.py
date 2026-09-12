"""
RSS feed sources for the News Intelligence Agent.

Each source has:
- name: Human-readable source name
- url: RSS feed URL
- category: Primary news category
- quality: Source quality score (1-10)
    10 = major international news agency (Reuters, AP, BBC)
    9 = established major publication
    8 = reputable specialist publication
    7 = established publication
    6 = smaller known publication
    5 = unknown / aggregator

To add a new source, simply append to RSS_SOURCES list.
"""

RSS_SOURCES = [
    # =========================================================
    # WORLD NEWS (quality 9-10)
    # =========================================================
    {
        "name": "Reuters World",
        "url": "https://feeds.reuters.com/Reuters/worldNews",
        "category": "WORLD",
        "quality": 10,
    },
    {
        "name": "BBC World",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "WORLD",
        "quality": 10,
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "category": "WORLD",
        "quality": 9,
    },

    # =========================================================
    # BUSINESS
    # =========================================================
    {
        "name": "BBC Business",
        "url": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "category": "BUSINESS",
        "quality": 10,
    },
    {
        "name": "CNBC Top News",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "category": "BUSINESS",
        "quality": 9,
    },

    # =========================================================
    # TECHNOLOGY
    # =========================================================
    {
        "name": "BBC Tech",
        "url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
        "category": "TECHNOLOGY",
        "quality": 10,
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "TECHNOLOGY",
        "quality": 8,
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "TECHNOLOGY",
        "quality": 8,
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "category": "TECHNOLOGY",
        "quality": 9,
    },
    {
        "name": "Wired",
        "url": "https://www.wired.com/feed/rss",
        "category": "TECHNOLOGY",
        "quality": 9,
    },

    # =========================================================
    # AI / ARTIFICIAL INTELLIGENCE
    # =========================================================
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "category": "AI",
        "quality": 9,
    },
    {
        "name": "VentureBeat",
        "url": "https://venturebeat.com/feed/",
        "category": "AI",
        "quality": 8,
    },

    # =========================================================
    # SCIENCE
    # =========================================================
    {
        "name": "BBC Science",
        "url": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "category": "SCIENCE",
        "quality": 10,
    },

    # =========================================================
    # SPACE
    # =========================================================
    {
        "name": "NASA Breaking News",
        "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "category": "SPACE",
        "quality": 10,
    },
    {
        "name": "Space.com",
        "url": "https://www.space.com/feeds/all",
        "category": "SPACE",
        "quality": 8,
    },

    # =========================================================
    # HEALTH
    # =========================================================
    {
        "name": "BBC Health",
        "url": "http://feeds.bbci.co.uk/news/health/rss.xml",
        "category": "HEALTH",
        "quality": 10,
    },

    # =========================================================
    # SPORTS
    # =========================================================
    {
        "name": "ESPN",
        "url": "https://www.espn.com/espn/rss/news",
        "category": "SPORTS",
        "quality": 9,
    },
    {
        "name": "BBC Sport",
        "url": "http://feeds.bbci.co.uk/sport/rss.xml",
        "category": "SPORTS",
        "quality": 10,
    },

    # =========================================================
    # ENTERTAINMENT
    # =========================================================
    {
        "name": "BBC Entertainment",
        "url": "http://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
        "category": "ENTERTAINMENT",
        "quality": 10,
    },

    # =========================================================
    # CRYPTO
    # =========================================================
    {
        "name": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "category": "CRYPTO",
        "quality": 8,
    },

    # =========================================================
    # CYBERSECURITY
    # =========================================================
    {
        "name": "The Hacker News",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "category": "CYBERSECURITY",
        "quality": 9,
    },

    # =========================================================
    # GOOGLE NEWS (aggregated — quality 7 as aggregator)
    # =========================================================
    {
        "name": "Google News Top Stories",
        "url": "https://news.google.com/rss",
        "category": "GENERAL",
        "quality": 7,
    },
    {
        "name": "Google News World",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB",
        "category": "WORLD",
        "quality": 7,
    },
    {
        "name": "Google News Technology",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB",
        "category": "TECHNOLOGY",
        "quality": 7,
    },
    {
        "name": "Google News Business",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB",
        "category": "BUSINESS",
        "quality": 7,
    },
    {
        "name": "Google News Science",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pWVXlnQVAB",
        "category": "SCIENCE",
        "quality": 7,
    },
    {
        "name": "Google News Sports",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pWVXlnQVAB",
        "category": "SPORTS",
        "quality": 7,
    },
    {
        "name": "Google News Health",
        "url": "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ",
        "category": "HEALTH",
        "quality": 7,
    },
    {
        "name": "Google News Entertainment",
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pWVXlnQVAB",
        "category": "ENTERTAINMENT",
        "quality": 7,
    },
]
