"""
News Intelligence Agent — Main Entry Point

Starts two components simultaneously:
1. Scheduled news collector (every 30 minutes)
2. FastAPI web server + dashboard (port 8000)

Usage:
    python main.py           # Start everything
    python main.py --once    # Run one collection and exit
"""

import sys
import threading
import argparse

from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from config.settings import (
    COLLECTION_INTERVAL_MINUTES,
    CLEANUP_INTERVAL_HOURS,
    API_HOST,
    API_PORT,
)
from database.supabase_client import NewsDatabase
from collectors.rss_collector import RSSCollector
from collectors.newsapi_collector import NewsAPICollector
from collectors.manager import CollectorManager
from processors.normalizer import ArticleNormalizer
from processors.deduplicator import Deduplicator
from processors.scorer import ArticleScorer
from processors.story_grouper import StoryGrouper
from ai.gemini_client import GeminiClient
from services.cache_service import CacheService
from services.top5_service import Top5Service
from services.breaking_service import BreakingService
from api.server import app as fastapi_app, init_api, init_research
from collectors.arxiv_collector import ArxivCollector
from processors.research_analyzer import ResearchAnalyzer
from utils.logger import get_logger

logger = get_logger("main")


def create_components():
    """Initialize all components and wire them together.

    Returns:
        Tuple of (collector_manager, top5_service, breaking_service, db)
    """
    logger.info("Initializing components...")

    # Core infrastructure
    db = NewsDatabase()
    gemini = GeminiClient()
    cache = CacheService()

    # Collectors
    rss = RSSCollector()
    newsapi = NewsAPICollector(db=db)

    # Processors
    normalizer = ArticleNormalizer()
    deduplicator = Deduplicator()
    scorer = ArticleScorer()
    grouper = StoryGrouper()

    # Services
    collector_manager = CollectorManager(
        db=db,
        rss_collector=rss,
        newsapi_collector=newsapi,
        normalizer=normalizer,
        deduplicator=deduplicator,
        scorer=scorer,
        story_grouper=grouper,
    )

    top5_service = Top5Service(
        db=db,
        gemini=gemini,
        cache=cache,
        story_grouper=grouper,
    )

    breaking_service = BreakingService(db=db)

    # Research
    arxiv = ArxivCollector(max_papers_per_category=10)
    research_analyzer = ResearchAnalyzer(gemini_client=gemini)

    # API
    init_api(
        top5_service=top5_service,
        db=db,
        collector_manager=collector_manager,
        breaking_service=breaking_service,
    )
    init_research(arxiv_collector=arxiv, research_analyzer=research_analyzer)

    logger.info("All components initialized ✓")
    return collector_manager, top5_service, breaking_service, db, arxiv, research_analyzer


def run_collection_once(collector_manager, breaking_service):
    """Run a single collection cycle.

    Args:
        collector_manager: CollectorManager instance.
        breaking_service: BreakingService instance.
    """
    results = collector_manager.collect()

    # Handle breaking news
    breaking = results.get("breaking_articles", [])
    if breaking:
        for article in breaking:
            new_alerts = breaking_service.detect([article])
            if new_alerts:
                logger.info(f"🚨 Breaking: {article.title}")
                breaking_service.mark_alerted(article)


def start_scheduler(collector_manager, breaking_service, arxiv_collector=None, research_analyzer=None):
    """Start the APScheduler for periodic news collection.

    Args:
        collector_manager: CollectorManager instance.
        breaking_service: BreakingService instance.
        arxiv_collector: ArxivCollector instance (optional).
        research_analyzer: ResearchAnalyzer instance (optional).
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()

    # News collection every 30 minutes
    scheduler.add_job(
        run_collection_once,
        'interval',
        minutes=COLLECTION_INTERVAL_MINUTES,
        args=[collector_manager, breaking_service],
        id='news_collector',
        name='News Collection',
        max_instances=1,  # Prevent overlapping runs
    )

    # Cleanup old articles every hour
    scheduler.add_job(
        collector_manager.db.cleanup_old_articles,
        'interval',
        hours=CLEANUP_INTERVAL_HOURS,
        id='cleanup',
        name='Article Cleanup',
        max_instances=1,
    )

    # Research paper fetch every 6 hours
    if arxiv_collector:
        from api.server import _db as research_db
        def _fetch_research():
            try:
                logger.info("Scheduled research paper fetch...")
                papers, failed = arxiv_collector.fetch_all()
                db = collector_manager.db
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
                        db.client.table("research_papers").upsert(
                            paper_data, on_conflict="arxiv_id"
                        ).execute()
                        stored += 1
                    except Exception:
                        pass
                logger.info(f"Scheduled research fetch: {stored} papers stored")
            except Exception as e:
                logger.warning(f"Scheduled research fetch failed: {e}")

        scheduler.add_job(
            _fetch_research,
            'interval',
            hours=6,
            id='research_collector',
            name='Research Paper Collection',
            max_instances=1,
        )

    scheduler.start()
    logger.info(
        f"Scheduler started: collection every {COLLECTION_INTERVAL_MINUTES} min, "
        f"cleanup every {CLEANUP_INTERVAL_HOURS} hr, research every 6 hr"
    )
    return scheduler


def start_fastapi_server():
    """Start the FastAPI server in a background thread."""
    import uvicorn

    def _run():
        uvicorn.run(
            fastapi_app,
            host=API_HOST,
            port=API_PORT,
            log_level="warning",  # Reduce uvicorn noise
        )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info(f"FastAPI server started at http://{API_HOST}:{API_PORT}")
    logger.info(f"  Dashboard: http://localhost:{API_PORT}")
    logger.info(f"  API docs:  http://localhost:{API_PORT}/docs")
    return thread


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="News Intelligence Agent")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one collection cycle and exit (no scheduler, no server)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  NEWS INTELLIGENCE AGENT")
    logger.info("  Multi-source AI news aggregation & ranking")
    logger.info("=" * 60)

    # Initialize all components
    collector_manager, top5_service, breaking_service, db, arxiv, research_analyzer = create_components()

    # ─── Single run mode ──────────────────────────────
    if args.once:
        logger.info("Running single collection (--once mode)...")
        run_collection_once(collector_manager, breaking_service)
        logger.info("Single collection complete. Exiting.")
        return

    # ─── Full server mode ─────────────────────────────
    # 1. Start FastAPI server FIRST so dashboard is available immediately
    api_thread = start_fastapi_server()

    # 2. Start scheduler (with research)
    scheduler = start_scheduler(
        collector_manager, breaking_service,
        arxiv_collector=arxiv, research_analyzer=research_analyzer,
    )

    # 3. Run initial collection in background thread
    def _initial_collection():
        logger.info("Running initial news collection...")
        run_collection_once(collector_manager, breaking_service)
        logger.info("Initial collection complete.")
    threading.Thread(target=_initial_collection, daemon=True).start()

    logger.info("Dashboard available at http://localhost:8000")
    logger.info("Press Ctrl+C to stop.")
    try:
        # Keep the main thread alive
        api_thread.join()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
