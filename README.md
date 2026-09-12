# 🔥 Autonomous News & Research Aggregation System with AI-Powered Analysis

> A multi-source, AI-powered news intelligence and research paper aggregation system that collects, processes, scores, and ranks news from **25+ sources** and research papers from **4 academic databases** — all presented through a beautiful dark-themed dashboard.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge\&logo=python\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge\&logo=fastapi\&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_3.6_Flash-4285F4?style=for-the-badge\&logo=google\&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge\&logo=supabase\&logoColor=white)

---

## 📑 Table of Contents

* [Overview](#overview)
* [System Architecture](#system-architecture)
* [Tech Stack](#tech-stack)
* [Features](#features)
* [Project Structure](#project-structure)
* [Component Deep Dive](#component-deep-dive)
* [Data Flow Pipeline](#data-flow-pipeline)
* [API Reference](#api-reference)
* [Quick Start](#quick-start)
* [Deployment](#deployment)
* [License](#license)

---

## Overview

This system operates as an **intelligent aggregation pipeline** that:

1. **Collects** news from 25+ RSS feeds, NewsAPI, and Google News
2. **Normalizes** raw data into a unified format
3. **Deduplicates** articles using URL + title similarity matching
4. **Scores** each article using a 6-factor weighted algorithm
5. **Groups** related articles into story clusters
6. **Verifies** authenticity using a 5-signal cross-reference check
7. **Presents** results via Gemini AI formatting on a web dashboard

For research, it pulls papers from **4 academic sources** (arXiv, Crossref, Semantic Scholar, OpenAlex) across 20 AI/ML categories and provides AI-powered analysis of each paper.

---

## System Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA COLLECTION LAYER                         │
├─────────────────┬──────────────────┬──────────────────┬─────────────┤
│   RSS Feeds     │    NewsAPI       │   arXiv RSS      │  Crossref   │
│   (25+ feeds)   │  (100 req/day)   │  (20 categories) │  (150M+)    │
│   feedparser    │    requests      │   feedparser     │  requests   │
├─────────────────┴──────────────────┼──────────────────┼─────────────┤
│        Semantic Scholar API        │    OpenAlex API   │             │
│        (200M+ papers)              │   (250M+ works)   │             │
└──────────────────┬─────────────────┴──────────────────┘             │
                   ▼                                                  │
┌─────────────────────────────────────────────────────────────────────┤
│                       PROCESSING PIPELINE                            │
├─────────────────┬──────────────────┬──────────────────┬─────────────┤
│   Normalizer    │  Deduplicator    │     Scorer       │  Grouper    │
│  Unified format │ URL + 50% title  │  6-factor algo   │ Story       │
│  + ISO dates    │  similarity      │  importance,     │ clustering  │
│  + categories   │  matching        │  recency, etc.   │ by topic    │
├─────────────────┴──────────────────┴──────────────────┴─────────────┤
│                    Authenticity Checker                              │
│   5-signal: source tier, corroboration, red flags, freshness, QA    │
└──────────────────┬──────────────────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                                │
│                   Supabase (PostgreSQL)                              │
│   • articles table (news, scores, grouping)                          │
│   • research_papers table (papers, analysis)                         │
│   • system_status table (health tracking)                            │
│   • alert_log table (breaking news)                                  │
│   Full-text search • RLS policies • Performance indexes              │
└──────────────────┬──────────────────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                              │
├──────────────────────────┬──────────────────────────────────────────┤
│  FastAPI REST API        │  Web Dashboard (HTML/CSS/JS)              │
│  • /api/top5             │  • Dark theme with glassmorphism          │
│  • /api/breaking         │  • Category filters + search              │
│  • /api/research         │  • Research papers tab                    │
│  • /api/query (chatbot)  │  • AI chatbot panel                      │
│  • Rate limiting (60/m)  │  • Live system status                    │
│  • CORS enabled          │  • Responsive layout                     │
├──────────────────────────┴──────────────────────────────────────────┤
│                    Gemini 3.6 Flash (AI Layer)                       │
│   • News formatting & presentation                                   │
│   • Research paper analysis                                          │
│   • Chatbot query responses                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Core Language & Framework

| Technology  | Version | Purpose                                                                              |
| ----------- | ------- | ------------------------------------------------------------------------------------ |
| **Python**  | 3.10+   | Core language — chosen for rich ecosystem of data processing, ML, and web libraries  |
| **FastAPI** | 0.115.0 | Async web framework — auto-generated Swagger docs, type validation, high performance |
| **Uvicorn** | 0.30.0  | ASGI server — runs FastAPI with async support                                        |

### Data Collection

| Technology            | Purpose                                                       | Why Chosen                                                |
| --------------------- | ------------------------------------------------------------- | --------------------------------------------------------- |
| **feedparser** 6.0.11 | Parses RSS/Atom feeds from 25+ news sources                   | Industry standard for feed parsing, handles malformed XML |
| **requests** 2.32.3   | HTTP client for NewsAPI, Crossref, Semantic Scholar, OpenAlex | Simple, reliable, connection pooling                      |
| **NewsAPI**           | 100 req/day (free) for real-time news                         | Covers major outlets, keyword + category search           |

### Academic Paper Sources (4 APIs)

| Source               | Papers | Auth Required            | Rate Limit |
| -------------------- | ------ | ------------------------ | ---------- |
| **arXiv**            | 2.4M+  | None                     | None       |
| **Crossref**         | 150M+  | None                     | None       |
| **Semantic Scholar** | 200M+  | None (free key optional) | ~1 req/sec |
| **OpenAlex**         | 250M+  | None                     | Generous   |

### AI & ML

| Technology                    | Purpose                                     | Why Chosen                                 |
| ----------------------------- | ------------------------------------------- | ------------------------------------------ |
| **Google Gemini 3.6 Flash**   | News formatting, research analysis, chatbot | Free tier, fast, good at structured output |
| **google-generativeai** 0.8.5 | Python SDK for Gemini API                   | Official Google SDK                        |

### Database

| Technology                | Purpose                                           | Why Chosen                          |
| ------------------------- | ------------------------------------------------- | ----------------------------------- |
| **Supabase** (PostgreSQL) | Persistent storage for articles + research papers | Free tier, real-time, REST API, RLS |
| **supabase-py** 2.15.0    | Python client for Supabase                        | Official SDK with CRUD + real-time  |

### Scheduling & Background Tasks

| Technology             | Purpose                                                  | Why Chosen                               |
| ---------------------- | -------------------------------------------------------- | ---------------------------------------- |
| **APScheduler** 3.11.0 | Periodic news collection, cleanup, and research fetching | Lightweight, cron + interval support     |
| **threading** (stdlib) | Background tasks                                         | Built-in, avoids blocking the API server |

### Security & Rate Limiting

| Technology          | Purpose                       | Why Chosen                             |
| ------------------- | ----------------------------- | -------------------------------------- |
| **slowapi** 0.1.10  | API rate limiting             | FastAPI-compatible, per-IP limiting    |
| **CORS middleware** | Cross-origin request handling | Required for external dashboard access |

### Configuration & Environment

| Technology              | Purpose                                         |
| ----------------------- | ----------------------------------------------- |
| **python-dotenv** 1.1.0 | Load `.env` file for API keys and configuration |
| **Pydantic**            | Request/response validation through FastAPI     |

### Frontend

| Technology               | Purpose                                                    |
| ------------------------ | ---------------------------------------------------------- |
| **HTML5**                | Semantic structure                                         |
| **CSS3**                 | Dark theme, glassmorphism, grid layouts, responsive design |
| **Vanilla JavaScript**   | Dynamic rendering, API calls, category filtering           |
| **Google Fonts (Inter)** | Modern typography                                          |

---

## Features

### 📰 News Intelligence

* **25+ News Sources** — BBC, Reuters, AP, TechCrunch, ESPN, NASA, CNBC, Wired, Ars Technica, and more
* **26 Categories** — World, Tech, AI, Business, Sports, Science, Health, Crypto, Space, Gaming, etc.
* **Smart Deduplication** — URL matching + 50% title word-overlap detection
* **Story Grouping** — Clusters related articles about the same event
* **6-Factor Scoring Algorithm** — Importance (35%), Recency (20%), Credibility (20%), Urgency (10%), Source Quality (10%), Category Boost (5%)
* **Breaking News Detection** — Auto-detects when importance ≥ 82 and urgency ≥ 75
* **Authenticity Checker** — 5-signal verification: source tier, corroboration, red flags, freshness, content quality

### 📚 Research Papers

* **4 Academic Sources** — arXiv, Crossref, Semantic Scholar, OpenAlex
* **AI-Powered Analysis** — Gemini analyzes each paper's abstract for key contributions
* **Category Grouping** — Papers organized by field with AI/ML prioritized
* **Publication Dates & Links** — DOI links, PDF downloads, abstract URLs
* **Source Badges** — Visual indicators for each paper's source

### 🎨 Dashboard

* **Dark Theme** — Premium dark design with glassmorphism effects
* **Category Filtering** — Click any category to filter news
* **Research Tab** — Browse and fetch research papers
* **AI Chatbot** — Natural language queries such as `/top5 ai`, `/breaking`, and `/status`
* **Live System Status** — Real-time collection statistics and source health
* **Responsive** — Works on desktop and mobile

### 🔧 API

* **REST API** with auto-generated Swagger documentation at `/docs`
* **Rate Limiting** — Per-IP limits prevent abuse
* **CORS** — Cross-origin access enabled
* **Health Check** — `/health` endpoint
* **Pagination** — Offset-based pagination on research endpoint

---

## Project Structure

```text
📁 New_Fetching_Agent/
│
├── 📄 main.py                         # Application entry point
│                                       # Initializes components and starts scheduler/server
│
├── 📁 config/                         # Configuration
│   ├── settings.py                    # Central config (API keys, weights, thresholds)
│   ├── rss_sources.py                 # 25+ RSS feed definitions with quality scores
│   └── newsapi_config.py              # NewsAPI categories + keyword queries
│
├── 📁 collectors/                     # Data Collection Layer
│   ├── manager.py                     # Orchestrates all collectors
│   ├── rss_collector.py               # Fetches from 25+ RSS feeds
│   ├── newsapi_collector.py           # NewsAPI integration
│   └── arxiv_collector.py             # arXiv + Crossref + Semantic Scholar + OpenAlex
│
├── 📁 processors/                     # Data Processing Pipeline
│   ├── normalizer.py                  # Raw data → unified article format
│   ├── deduplicator.py                # URL + title similarity deduplication
│   ├── scorer.py                      # 6-factor weighted scoring algorithm
│   ├── story_grouper.py               # Clusters related articles
│   ├── authenticity_checker.py        # 5-signal source verification
│   └── research_analyzer.py           # Gemini-powered paper analysis
│
├── 📁 database/                       # Storage Layer
│   ├── supabase_client.py             # Supabase CRUD operations
│   ├── models.py                      # Article data models
│   ├── schema.sql                     # News database schema
│   └── schema_research.sql            # Research papers schema
│
├── 📁 ai/                             # AI Layer
│   ├── gemini_client.py               # Gemini client with fallback
│   └── prompts.py                     # System + user prompt templates
│
├── 📁 services/                       # Business Logic Layer
│   ├── top5_service.py                # Top news aggregation + query handling
│   ├── breaking_service.py            # Breaking news detection + alerts
│   └── cache_service.py               # In-memory cache (5-min TTL)
│
├── 📁 api/                            # API Layer
│   ├── server.py                      # FastAPI routes, CORS, rate limiting
│   └── __init__.py                    # Service injection helpers
│
├── 📁 dashboard/                      # Frontend
│   ├── index.html                     # Main dashboard page
│   ├── style.css                      # Dark theme + glassmorphism styles
│   ├── script.js                      # Dynamic rendering + API integration
│   └── robots.txt                     # SEO robots file
│
├── 📁 utils/                          # Utilities
│   ├── logger.py                      # Colored console logging
│   └── timezone_utils.py              # Timezone-aware date handling
│
├── 📁 bot/                            # Reserved for Telegram bot
│
├── 📄 requirements.txt                # Python dependencies
├── 📄 .env.example                    # Environment variable template
└── 📄 .gitignore                      # Git ignore rules
```

---

## Component Deep Dive

### 1. RSS Collector (`collectors/rss_collector.py`)

Fetches news from 25+ RSS/Atom feeds using `feedparser`. Each source is assigned a **quality score (1–10)** that feeds into the credibility algorithm.

**Sources include:** Reuters (10), BBC (10), AP News (10), TechCrunch (8), ESPN (8), NASA (8), CNBC (9), Wired (8), Ars Technica (8), The Verge (7), and more.

### 2. NewsAPI Collector (`collectors/newsapi_collector.py`)

Manages a daily budget of **100 free API requests**:

* 41 requests reserved for scheduled category fetches
* 59 requests reserved for on-demand user queries
* Tracks daily usage
* Resets at midnight

### 3. Research Paper Collector (`collectors/arxiv_collector.py`)

Fetches from **4 academic APIs**:

| Source               | Method                            | Papers/Fetch |
| -------------------- | --------------------------------- | ------------ |
| **arXiv**            | RSS feeds across 20 CS categories | ~40          |
| **Crossref**         | REST API with 5 AI/ML queries     | ~14          |
| **Semantic Scholar** | REST API with rate-limit handling | ~9           |
| **OpenAlex**         | REST API sorted by citation count | ~9           |

Cross-deduplicates papers by title similarity to avoid duplicates across sources.

### 4. Scoring Algorithm (`processors/scorer.py`)

Each article receives a **0–100 final score** based on six weighted factors:

```text
final_score = (importance × 0.35) + (recency × 0.20) + (credibility × 0.20)
            + (urgency × 0.10) + (source_quality × 0.10) + (category_boost × 0.05)
```

Factors:

* **Importance** — Based on category weight + keyword analysis
* **Recency** — Exponential decay, where newer articles receive higher scores
* **Credibility** — Source quality score × corroboration factor
* **Urgency** — Breaking-news keyword detection
* **Source Quality** — Publisher reputation on a 1–10 scale
* **Category Boost** — Priority categories receive an additional bonus

### 5. Authenticity Checker (`processors/authenticity_checker.py`)

Five-signal verification system:

| Signal          | What It Checks                                      |
| --------------- | --------------------------------------------------- |
| Source Tier     | Tier-1 sources vs. unknown sources                  |
| Corroboration   | Number of other sources reporting the same story    |
| Red Flags       | Clickbait patterns, excessive punctuation, ALL CAPS |
| Freshness       | Whether the article is recent                       |
| Content Quality | Title, description, and URL quality                 |

### 6. Gemini AI Integration (`ai/gemini_client.py`)

Uses Gemini for:

* Formatting top news into readable presentations
* Analyzing research paper abstracts
* Responding to chatbot queries

Includes a **deterministic fallback**, allowing the system to continue functioning with template-based formatting if Gemini is unavailable.

---

## Data Flow Pipeline

```text
[User clicks "Fetch News"]
        ↓
[RSS Feeds] + [NewsAPI] → Raw articles
        ↓
[Normalizer] → Unified format
        ↓
[Deduplicator] → Remove duplicates
        ↓
[Scorer] → Each article gets 0–100 score
        ↓
[Story Grouper] → Related articles clustered
        ↓
[Authenticity Checker] → Verification signals
        ↓
[Supabase PostgreSQL] → Stored with scores, groups, flags
        ↓
[Gemini 3.6 Flash] → AI formatting for presentation
        ↓
[Dashboard] → User sees top 20 ranked stories
```

---

## API Reference

| Endpoint                   | Method | Rate Limit | Description                                   |
| -------------------------- | ------ | ---------- | --------------------------------------------- |
| `/health`                  | GET    | —          | Health check (`{"status": "ok"}`)             |
| `/api/top5`                | GET    | 60/min     | Top 20 news (`?category=AI&hours=6&limit=20`) |
| `/api/breaking`            | GET    | 60/min     | Breaking news alerts                          |
| `/api/latest`              | GET    | 60/min     | Most recently collected articles              |
| `/api/status`              | GET    | —          | System health and statistics                  |
| `/api/categories`          | GET    | —          | Available news categories                     |
| `/api/query`               | POST   | 30/min     | Chatbot query (`{"message": "/top5 ai"}`)     |
| `/api/collect`             | POST   | 5/min      | Trigger on-demand collection                  |
| `/api/research`            | GET    | 60/min     | Research papers (`?limit=20&offset=0`)        |
| `/api/research/refresh`    | POST   | 3/min      | Fetch new papers from all sources             |
| `/api/research/categories` | GET    | —          | Available arXiv categories                    |
| `/docs`                    | GET    | —          | Swagger API documentation                     |

---

## Quick Start

### Prerequisites

* Python 3.10+
* A Supabase project
* NewsAPI key
* Google Gemini API key

### 1. Get API Keys

The following services provide free or free-tier access:

| Service       | Link                                                      | Free Tier         |
| ------------- | --------------------------------------------------------- | ----------------- |
| Supabase      | [supabase.com](https://supabase.com)                      | Free project tier |
| NewsAPI       | [newsapi.org/register](https://newsapi.org/register)      | 100 requests/day  |
| Google Gemini | [aistudio.google.com](https://aistudio.google.com/apikey) | Free API tier     |

### 2. Setup Database

1. Create a Supabase project.
2. Open the **SQL Editor**.
3. Run:

```text
database/schema.sql
```

4. Run:

```text
database/schema_research.sql
```

### 3. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
NEWSAPI_KEY=your-newsapi-key
GEMINI_API_KEY=your-gemini-api-key
API_HOST=127.0.0.1
API_PORT=8000
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Application

```bash
python main.py
```

### 6. Access the Application

* **Dashboard:** `http://localhost:8000`
* **API Docs:** `http://localhost:8000/docs`
* **Health Check:** `http://localhost:8000/health`

---

## Deployment

Set:

```env
API_HOST=0.0.0.0
```

in `.env` for external access.

### Render

1. Push the project to GitHub.
2. Create a new Web Service on Render.
3. Connect the GitHub repository.
4. Use the following build command:

```bash
pip install -r requirements.txt
```

5. Use the following start command:

```bash
python main.py
```

6. Add the required environment variables in the Render dashboard.

### Other Deployment Options

| Platform    | Cost                      | Notes                               |
| ----------- | ------------------------- | ----------------------------------- |
| **Render**  | Free tier                 | Suitable for lightweight deployment |
| **Koyeb**   | Free tier                 | Alternative hosting option          |
| **Fly.io**  | Paid/free allowances vary | Docker-based deployment             |
| **Railway** | Usage-based               | Simple application deployment       |

---

## License

MIT
