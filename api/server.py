"""
FastAPI server for the News Intelligence Agent.

Provides REST API endpoints and serves the web dashboard.
Runs alongside the scheduler. Includes SSE endpoint for
real-time progress tracking.
"""

import asyncio
from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import threading

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from utils.logger import get_logger

logger = get_logger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# FastAPI app instance
app = FastAPI(
    title="News Intelligence Agent",
    description="Multi-source AI news aggregation and ranking system",
    version="1.0.0",
)

# CORS — allow all origins for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global references to services (set by main.py)
_top5_service = None
_db = None
_collector_manager = None
_breaking_service = None
_is_collecting = False  # Lock to prevent parallel collections


class QueryRequest(BaseModel):
    """Request body for the chatbot query endpoint."""
    message: str


def init_api(top5_service, db, collector_manager=None, breaking_service=None):
    """Inject service dependencies into the API.

    Called by main.py after services are initialized.

    Args:
        top5_service: Top5Service instance.
        db: NewsDatabase instance.
        collector_manager: CollectorManager instance (for on-demand collection).
        breaking_service: BreakingService instance.
    """
    global _top5_service, _db, _collector_manager, _breaking_service
    _top5_service = top5_service
    _db = db
    _collector_manager = collector_manager
    _breaking_service = breaking_service
    logger.info("FastAPI services initialized")


# =============================================================
# API Endpoints
# =============================================================

@app.get("/health")
async def health_check():
    """Simple health check for deployment platforms."""
    return {"status": "ok"}


@app.get("/api/top5")
@limiter.limit("60/minute")
async def get_top5(request: Request,
    category: Optional[str] = Query(None, description="Category filter (ai, world, tech, sports, etc.)"),
    hours: int = Query(168, description="Time range in hours (default 7 days)", ge=1, le=168),
    limit: int = Query(20, description="Number of stories", ge=1, le=20),
):
    """Get the top N most important news stories.

    Returns formatted text and structured data.
    """
    if not _top5_service:
        return JSONResponse(
            status_code=503,
            content={"error": "Service not ready. Please wait for initialization."},
        )

    # Normalize category
    cat = category.upper() if category else None

    # Get formatted text
    formatted = _top5_service.get_top5(
        category=cat,
        time_hours=hours,
        limit=limit,
    )

    # Also get raw data for the dashboard
    articles = []
    if _db:
        raw = _db.get_top_articles(category=cat, time_hours=hours, limit=30)
        from processors.story_grouper import StoryGrouper
        grouper = StoryGrouper()
        unique = grouper.get_primary_per_group(raw)
        articles = unique[:limit]

    return {
        "formatted": formatted,
        "articles": articles,
        "count": len(articles),
        "category": cat,
        "time_hours": hours,
    }


@app.get("/api/breaking")
@limiter.limit("60/minute")
async def get_breaking(request: Request):
    """Get current breaking news."""
    if not _top5_service:
        return JSONResponse(status_code=503, content={"error": "Service not ready."})

    formatted = _top5_service.get_breaking()

    articles = []
    if _db:
        articles = _db.get_top_articles(time_hours=6, limit=5, breaking_only=True)

    return {
        "formatted": formatted,
        "articles": articles,
        "count": len(articles),
    }


@app.get("/api/latest")
@limiter.limit("60/minute")
async def get_latest(request: Request, limit: int = Query(5, ge=1, le=20)):
    """Get the most recently collected articles."""
    if not _top5_service:
        return JSONResponse(status_code=503, content={"error": "Service not ready."})

    articles = []
    if _db:
        articles = _db.get_latest_articles(limit=limit)

    formatted = _top5_service.get_latest(limit=limit)

    return {
        "formatted": formatted,
        "articles": articles,
        "count": len(articles),
    }


@app.get("/api/status")
async def get_status():
    """Get system health status."""
    if not _db:
        return {"status": "offline", "message": "Database not connected"}

    status = _db.get_status()

    # Add article count
    status["article_count"] = _db.get_article_count()

    return status


@app.get("/api/categories")
async def get_categories():
    """Get available news categories."""
    from config.settings import ALL_CATEGORIES
    return {"categories": ALL_CATEGORIES}


# =============================================================
# Chatbot Query Endpoint
# =============================================================

@app.post("/api/query")
@limiter.limit("30/minute")
async def handle_query(request: Request, body: QueryRequest):
    """Handle a natural language query from the chatbot.

    Accepts commands like /top5, /breaking, /status,
    or natural language like 'Top 5 AI news from last 6 hours'.

    Returns formatted text response.
    """
    if not _top5_service:
        return JSONResponse(status_code=503, content={"error": "Service not ready."})

    message = body.message.strip()
    if not message:
        return {"response": "Please enter a command or question."}

    logger.info(f"Chatbot query: {message[:80]}")

    response = _top5_service.handle_query(message)

    return {"response": response}


# =============================================================
# On-Demand Collection Endpoint
# =============================================================

@app.post("/api/collect")
@limiter.limit("5/minute")
async def trigger_collection(request: Request):
    """Trigger an on-demand news collection run.

    Runs collection in a background thread to avoid blocking the API.
    Returns immediately with a status message.
    """
    global _is_collecting

    if not _collector_manager:
        return JSONResponse(
            status_code=503,
            content={"error": "Collector not initialized."},
        )

    if _is_collecting:
        return {"status": "already_running", "message": "A collection is already in progress."}

    def _run_collection():
        global _is_collecting
        _is_collecting = True
        try:
            logger.info("On-demand collection triggered from dashboard")
            results = _collector_manager.collect()
            logger.info(
                f"On-demand collection complete: {results.get('stored_count', 0)} articles stored"
            )
        except Exception as e:
            logger.error(f"On-demand collection failed: {e}")
        finally:
            _is_collecting = False

    thread = threading.Thread(target=_run_collection, daemon=True)
    thread.start()

    return {"status": "started", "message": "News collection started. Results will appear shortly."}


@app.get("/api/collect/status")
async def collection_status():
    """Check if a collection is currently running, with current progress."""
    from services.progress_tracker import get_tracker
    tracker = get_tracker()

    result = {
        "is_collecting": tracker.is_running or _is_collecting,
        "is_fetching_papers": _is_fetching_papers,
    }

    # Include current progress event if available
    if tracker._current_event:
        from dataclasses import asdict
        result["progress"] = asdict(tracker._current_event)

    return result


@app.get("/api/collect/progress")
async def collect_progress_sse(request: Request):
    """Server-Sent Events endpoint for real-time collection progress.

    Streams progress events as they happen during news collection.
    The client connects once and receives updates automatically.
    """
    from services.progress_tracker import get_tracker

    tracker = get_tracker()
    queue = tracker.subscribe()

    async def event_stream():
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Non-blocking check for events
                try:
                    event = queue.get_nowait()
                    yield f"data: {event.to_json()}\n\n"

                    # Stop streaming after completion or error
                    if event.status in ("completed", "error"):
                        break
                except Exception:
                    # No event available, send keepalive
                    yield ": keepalive\n\n"

                await asyncio.sleep(0.5)
        finally:
            tracker.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================
# Research Papers Endpoints
# =============================================================

_arxiv_collector = None
_research_analyzer = None
_is_fetching_papers = False


def init_research(arxiv_collector, research_analyzer):
    """Inject research service dependencies."""
    global _arxiv_collector, _research_analyzer
    _arxiv_collector = arxiv_collector
    _research_analyzer = research_analyzer
    logger.info("Research services initialized")


@app.get("/api/research")
@limiter.limit("60/minute")
async def get_research(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by arXiv category code (e.g., cs.AI)"),
    priority: Optional[int] = Query(None, description="Filter by priority (1=AI/ML, 2=Tech, 3=Broader)"),
    limit: int = Query(20, description="Number of papers", ge=1, le=100),
    offset: int = Query(0, description="Pagination offset", ge=0),
):
    """Get analyzed research papers."""
    if not _db:
        return JSONResponse(status_code=503, content={"error": "Database not ready."})

    try:
        query = _db.client.table("research_papers").select("*").order(
            "published_at", desc=True
        ).range(offset, offset + limit - 1)

        if category:
            query = query.eq("primary_category", category)
        if priority:
            query = query.eq("priority", priority)

        result = query.execute()
        papers = result.data if result.data else []

        return {
            "papers": papers,
            "count": len(papers),
            "offset": offset,
            "limit": limit,
            "category": category,
            "priority": priority,
        }
    except Exception as e:
        error_str = str(e)
        if "research_papers" in error_str and ("does not exist" in error_str or "PGRST205" in error_str):
            return JSONResponse(
                status_code=503,
                content={"error": "Research papers table not created yet. Run database/schema_research.sql in Supabase SQL Editor."},
            )
        logger.error(f"Research query failed: {e}")
        return JSONResponse(status_code=500, content={"error": error_str})


@app.post("/api/research/refresh")
@limiter.limit("3/minute")
async def refresh_research(request: Request):
    """Trigger on-demand research paper fetch + analysis."""
    global _is_fetching_papers

    if not _arxiv_collector:
        return JSONResponse(status_code=503, content={"error": "arXiv collector not initialized."})

    if _is_fetching_papers:
        return {"status": "already_running", "message": "Paper fetch already in progress."}

    def _run_fetch():
        global _is_fetching_papers
        _is_fetching_papers = True
        try:
            logger.info("On-demand research paper fetch triggered")
            papers, failed = _arxiv_collector.fetch_all()

            # Store ALL papers immediately (so dashboard shows results fast)
            stored = 0
            for paper in papers:
                try:
                    paper_data = {
                        "arxiv_id": paper["arxiv_id"],
                        "title": paper["title"],
                        "abstract": paper.get("abstract", ""),
                        "authors": paper.get("authors", []),
                        "published_at": paper.get("published_at"),
                        "collected_at": paper.get("collected_at"),
                        "pdf_url": paper.get("pdf_url"),
                        "abs_url": paper.get("abs_url"),
                        "primary_category": paper.get("primary_category"),
                        "category_name": paper.get("category_name"),
                        "priority": paper.get("priority", 3),
                        "all_categories": paper.get("all_categories", []),
                        "analysis": paper.get("analysis", {}),
                        "is_analyzed": False,
                    }
                    _db.client.table("research_papers").upsert(
                        paper_data, on_conflict="arxiv_id"
                    ).execute()
                    stored += 1
                except Exception as e:
                    logger.debug(f"Failed to store paper {paper.get('arxiv_id')}: {e}")

            logger.info(f"Research fetch complete: {stored} papers stored")
        except Exception as e:
            logger.error(f"Research fetch failed: {e}")
        finally:
            _is_fetching_papers = False

    thread = threading.Thread(target=_run_fetch, daemon=True)
    thread.start()

    return {"status": "started", "message": "Fetching research papers from arXiv..."}


@app.get("/api/research/categories")
async def get_research_categories():
    """Get available arXiv categories."""
    from collectors.arxiv_collector import ARXIV_CATEGORIES
    return {"categories": ARXIV_CATEGORIES}


# =============================================================
# Dashboard Serving
# =============================================================

@app.get("/")
async def serve_dashboard():
    """Serve the web dashboard."""
    dashboard_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "dashboard",
        "index.html",
    )
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return JSONResponse(
        content={"message": "Dashboard not found. API is running at /docs"},
    )


@app.get("/robots.txt")
async def serve_robots():
    """Serve robots.txt."""
    robots_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "dashboard", "robots.txt"
    )
    if os.path.exists(robots_path):
        return FileResponse(robots_path, media_type="text/plain")
    return JSONResponse(content={"message": "Not found"}, status_code=404)


# Mount static files for dashboard assets (CSS, JS)
dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
if os.path.isdir(dashboard_dir):
    app.mount("/static", StaticFiles(directory=dashboard_dir), name="static")
