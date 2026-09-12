# News Intelligence Agent

A multi-source AI-powered news aggregation and ranking system that continuously collects, processes, and ranks news from 25+ sources across every major category. Also fetches and analyzes research papers from arXiv and Semantic Scholar.

**Open the dashboard and see the top 20 most important stories right now.**

## Features

- **Multi-Source Collection** — RSS feeds, NewsAPI, Google News
- **25+ News Sources** — BBC, Reuters, TechCrunch, ESPN, NASA, CNBC, and more
- **All Categories** — World, Tech, AI, Business, Sports, Science, Health, Crypto, Space, etc.
- **Smart Deduplication** — URL + title similarity removes duplicate coverage
- **Story Grouping** — Multiple articles about the same event are grouped together
- **Authenticity Checker** — 5-signal verification: source tier, corroboration, red flags, freshness, quality
- **Deterministic Scoring** — Importance, urgency, recency, credibility — no AI needed
- **Gemini AI Presentation** — Google Gemini 3.6 Flash formats the final output
- **Breaking News Detection** — Automatic detection when importance ≥ 82
- **Research Papers** — Fetches from 20 arXiv categories + Semantic Scholar with AI analysis
- **Web Dashboard** — Beautiful dark-themed dashboard at `localhost:8000`
- **REST API** — FastAPI with auto-generated Swagger docs, rate limiting, CORS
- **Zero Cost** — Runs entirely on free tiers

## Architecture

```
RSS Feeds (25+) ──→ Collector ──→ Normalizer ──→ Deduplicator ──→ Scorer
NewsAPI (100/day) ─┘                                                ↓
                                                              Story Grouper
                                                              Authenticity ←── Cross-source check
                                                                    ↓
                                                            Supabase PostgreSQL
                                                                    ↓
                                                               FastAPI
                                                              Dashboard
                                                                    ↓
                                                          localhost:8000
                                                                    ↓
                                                        Gemini 3.6 Flash
                                                           (formatting)
                                                                    ↓
                                                          📰 Top 20 News

arXiv (20 categories) ──→ Research Collector ──→ Semantic Scholar
                                                        ↓
                                                 Research Analyzer (Gemini)
                                                        ↓
                                                 📚 Research Papers Tab

### 1. Install & Run

```bash
pip install -r requirements.txt
python main.py
```

### 5. Access

- **Dashboard:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check for deployment |
| `/api/top5` | GET | Top 20 news (`?category=AI&hours=6&limit=20`) |
| `/api/breaking` | GET | Breaking news |
| `/api/latest` | GET | Most recent articles |
| `/api/status` | GET | System health |
| `/api/categories` | GET | Available categories |
| `/api/query` | POST | Chatbot query |
| `/api/collect` | POST | Trigger on-demand collection |
| `/api/research` | GET | Research papers (`?priority=1&limit=20&offset=0`) |
| `/api/research/refresh` | POST | Fetch new papers from arXiv + Semantic Scholar |
| `/api/research/categories` | GET | Available arXiv categories |
| `/docs` | GET | Swagger API documentation |

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Most GET endpoints | 60/min per IP |
| POST /api/query | 30/min per IP |
| POST /api/collect | 5/min per IP |
| POST /api/research/refresh | 3/min per IP |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| News Sources | feedparser, requests |
| Research | arXiv RSS, Semantic Scholar API |
| Database | Supabase (PostgreSQL) |
| AI | Google Gemini 3.6 Flash |
| Web Server | FastAPI + Uvicorn |
| Scheduler | APScheduler |
| Rate Limiting | slowapi |

## Project Structure

```
New_Fetching_Agent/
├── main.py                    # Entry point
├── config/                    # Settings, RSS sources, NewsAPI config
├── collectors/                # RSS, NewsAPI, arXiv, Semantic Scholar
├── processors/                # Normalizer, deduplicator, scorer, grouper, authenticity
├── database/                  # Supabase client, models, schema
├── ai/                        # Gemini client + prompts
├── services/                  # Top 20 service, breaking news, cache
├── api/                       # FastAPI server (CORS, rate limiting)
└── dashboard/                 # Web UI (HTML/CSS/JS)
```

## Deployment


## License

MIT
