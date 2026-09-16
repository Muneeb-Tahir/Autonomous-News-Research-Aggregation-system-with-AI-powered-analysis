"""
Phase 1 — Baseline Measurement & Article Export

This script:
1. Connects to Supabase
2. Measures all Stage 0 baseline metrics
3. Exports articles to CSV for Kaggle
4. Generates a baseline_report.json with all measurements

Run: python scripts/baseline_measurement.py
"""

import os
import sys
import json
import csv
import time
from datetime import datetime, timezone
from collections import Counter

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    SUPABASE_URL, SUPABASE_KEY, ALL_CATEGORIES,
    TITLE_SIMILARITY_THRESHOLD, CATEGORY_WEIGHTS
)
from supabase import create_client


def connect_db():
    """Connect to Supabase and return client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)
    
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"✅ Connected to Supabase")
    return client


def fetch_all_articles(client, batch_size=1000):
    """Fetch ALL articles from Supabase (handles pagination).
    
    Supabase limits responses to ~1000 rows, so we paginate.
    """
    all_articles = []
    offset = 0
    
    while True:
        response = (
            client.table("articles")
            .select("*")
            .order("collected_at", desc=False)
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        
        batch = response.data or []
        if not batch:
            break
        
        all_articles.extend(batch)
        offset += len(batch)
        print(f"   Fetched {len(all_articles)} articles so far...")
        
        if len(batch) < batch_size:
            break
    
    print(f"✅ Total articles fetched: {len(all_articles)}")
    return all_articles


def measure_baseline(articles):
    """Calculate all Stage 0 baseline metrics."""
    
    if not articles:
        print("❌ No articles found in database!")
        return {}
    
    metrics = {}
    
    # --- 1. Total count ---
    metrics["total_articles"] = len(articles)
    
    # --- 2. Category distribution ---
    categories = Counter(a.get("category", "UNKNOWN") for a in articles)
    metrics["category_distribution"] = dict(categories.most_common())
    metrics["num_categories_used"] = len(categories)
    metrics["most_common_category"] = categories.most_common(1)[0] if categories else ("NONE", 0)
    metrics["least_common_category"] = categories.most_common()[-1] if categories else ("NONE", 0)
    
    # --- 3. Source distribution ---
    sources = Counter(a.get("source_name", "Unknown") for a in articles)
    metrics["num_unique_sources"] = len(sources)
    metrics["top_10_sources"] = dict(sources.most_common(10))
    
    # --- 4. Processing stats ---
    processed = sum(1 for a in articles if a.get("is_processed", False))
    unprocessed = len(articles) - processed
    metrics["processed_articles"] = processed
    metrics["unprocessed_articles"] = unprocessed
    metrics["processing_rate"] = round(processed / len(articles) * 100, 1) if articles else 0
    
    # --- 5. Breaking news stats ---
    breaking = sum(1 for a in articles if a.get("is_breaking", False))
    metrics["breaking_articles"] = breaking
    metrics["breaking_rate"] = round(breaking / len(articles) * 100, 2) if articles else 0
    
    # --- 6. Score distribution ---
    scores = [a.get("final_score", 0) for a in articles if a.get("is_processed")]
    if scores:
        metrics["score_stats"] = {
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "mean": round(sum(scores) / len(scores), 2),
            "median": round(sorted(scores)[len(scores) // 2], 2),
        }
    
    # --- 7. Story grouping stats ---
    story_groups = set(a.get("story_group_id") for a in articles if a.get("story_group_id"))
    articles_with_groups = sum(1 for a in articles if a.get("story_group_id"))
    metrics["unique_story_groups"] = len(story_groups)
    metrics["articles_in_story_groups"] = articles_with_groups
    metrics["story_group_rate"] = round(
        articles_with_groups / len(articles) * 100, 1
    ) if articles else 0
    
    # --- 8. Time range ---
    dates = []
    for a in articles:
        pub = a.get("published_at") or a.get("collected_at")
        if pub:
            dates.append(pub)
    
    if dates:
        dates.sort()
        metrics["date_range"] = {
            "earliest": dates[0],
            "latest": dates[-1],
        }
    
    # --- 9. Content quality ---
    has_description = sum(1 for a in articles if a.get("description") and len(a["description"]) > 20)
    has_content = sum(1 for a in articles if a.get("content") and len(a["content"]) > 50)
    has_author = sum(1 for a in articles if a.get("author"))
    has_image = sum(1 for a in articles if a.get("image_url"))
    
    metrics["content_quality"] = {
        "with_description": has_description,
        "with_content": has_content,
        "with_author": has_author,
        "with_image": has_image,
        "description_rate": round(has_description / len(articles) * 100, 1),
        "content_rate": round(has_content / len(articles) * 100, 1),
    }
    
    # --- 10. Rule-based classification summary ---
    # This measures the CURRENT rule-based system's output
    # Later, ML classification will be compared against this
    metrics["rule_based_classification"] = {
        "method": "keyword matching in processors/normalizer.py",
        "categories_used": list(categories.keys()),
        "note": "These are the labels assigned by the existing rule-based system. "
                "ML classification will be compared against a manually-verified gold set."
    }
    
    # --- 11. Language distribution ---
    langs = Counter(a.get("language", "unknown") for a in articles)
    metrics["language_distribution"] = dict(langs)
    
    return metrics


def export_to_csv(articles, output_path):
    """Export articles to CSV for Kaggle upload."""
    
    if not articles:
        print("❌ No articles to export!")
        return
    
    # Fields to export (everything needed for ML/RAG)
    fields = [
        "id", "url", "title", "description", "content",
        "source_name", "source_quality", "category", "author",
        "published_at", "collected_at", "language",
        "importance_score", "urgency_score", "recency_score",
        "credibility_score", "final_score",
        "story_group_id", "is_breaking", "is_processed",
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        
        for article in articles:
            # Clean data for CSV
            row = {}
            for field in fields:
                val = article.get(field, "")
                if val is None:
                    val = ""
                if isinstance(val, (list, dict)):
                    val = json.dumps(val)
                row[field] = val
            writer.writerow(row)
    
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Exported {len(articles)} articles to {output_path} ({file_size_mb:.1f} MB)")


def print_report(metrics):
    """Print a formatted baseline report to console."""
    
    print("\n" + "=" * 60)
    print("  📊 STAGE 0 — BASELINE MEASUREMENT REPORT")
    print("=" * 60)
    
    print(f"\n📰 Total Articles: {metrics.get('total_articles', 0)}")
    print(f"🏷️  Categories Used: {metrics.get('num_categories_used', 0)}")
    print(f"📡 Unique Sources: {metrics.get('num_unique_sources', 0)}")
    
    print(f"\n✅ Processed: {metrics.get('processed_articles', 0)} ({metrics.get('processing_rate', 0)}%)")
    print(f"⏳ Unprocessed: {metrics.get('unprocessed_articles', 0)}")
    print(f"🔴 Breaking: {metrics.get('breaking_articles', 0)} ({metrics.get('breaking_rate', 0)}%)")
    
    if "score_stats" in metrics:
        s = metrics["score_stats"]
        print(f"\n📈 Score Stats: min={s['min']}, max={s['max']}, mean={s['mean']}, median={s['median']}")
    
    print(f"\n📂 Story Groups: {metrics.get('unique_story_groups', 0)}")
    print(f"   Articles in groups: {metrics.get('articles_in_story_groups', 0)} ({metrics.get('story_group_rate', 0)}%)")
    
    if "date_range" in metrics:
        d = metrics["date_range"]
        print(f"\n📅 Date Range: {d['earliest'][:10]} → {d['latest'][:10]}")
    
    if "content_quality" in metrics:
        cq = metrics["content_quality"]
        print(f"\n📝 Content Quality:")
        print(f"   With description: {cq['with_description']} ({cq['description_rate']}%)")
        print(f"   With full content: {cq['with_content']} ({cq['content_rate']}%)")
        print(f"   With author: {cq['with_author']}")
        print(f"   With image: {cq['with_image']}")
    
    print(f"\n🏷️  Category Distribution:")
    for cat, count in metrics.get("category_distribution", {}).items():
        bar = "█" * min(count, 50)
        print(f"   {cat:20s} {count:4d} {bar}")
    
    print(f"\n📡 Top 10 Sources:")
    for src, count in metrics.get("top_10_sources", {}).items():
        print(f"   {src:30s} {count:4d}")
    
    print("\n" + "=" * 60)


def main():
    """Run Phase 1: Baseline measurement + article export."""
    
    print("🚀 Phase 1 — Baseline Measurement & Article Export")
    print("-" * 50)
    
    # Step 1: Connect
    client = connect_db()
    
    # Step 2: Fetch all articles
    print("\n📥 Fetching all articles from Supabase...")
    start_time = time.time()
    articles = fetch_all_articles(client)
    fetch_time = time.time() - start_time
    print(f"   Fetch time: {fetch_time:.1f}s")
    
    if not articles:
        print("\n❌ No articles in database. Run your system first to collect articles.")
        print("   Run: python main.py")
        return
    
    # Step 3: Measure baseline
    print("\n📊 Measuring baseline metrics...")
    metrics = measure_baseline(articles)
    metrics["fetch_time_seconds"] = round(fetch_time, 2)
    metrics["measurement_timestamp"] = datetime.now(timezone.utc).isoformat()
    
    # Step 4: Print report
    print_report(metrics)
    
    # Step 5: Save metrics to JSON
    os.makedirs("data", exist_ok=True)
    metrics_path = os.path.join("data", "baseline_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"\n💾 Metrics saved to: {metrics_path}")
    
    # Step 6: Export to CSV
    csv_path = os.path.join("data", "articles_export.csv")
    export_to_csv(articles, csv_path)
    
    # Step 7: Summary
    print(f"\n✅ Phase 1 Complete!")
    print(f"   📊 Baseline metrics: {metrics_path}")
    print(f"   📄 Articles CSV:     {csv_path}")
    print(f"\n👉 Next step: Upload {csv_path} to Kaggle as a dataset")


if __name__ == "__main__":
    main()
