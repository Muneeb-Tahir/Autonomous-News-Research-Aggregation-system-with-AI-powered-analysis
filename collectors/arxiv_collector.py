"""
arXiv research paper collector for the News Intelligence Agent.

Fetches latest papers from arXiv RSS feeds across 20 CS/tech categories.
AI/ML categories are top priority.
"""

import feedparser
import re
from typing import List, Dict, Tuple
from datetime import datetime, timezone

from utils.logger import get_logger

logger = get_logger(__name__)


# ─── arXiv Categories (20 total) ─────────────────────────────
# Priority: 1 = Top (AI/ML), 2 = High (Core Tech), 3 = Medium (Broader)
ARXIV_CATEGORIES = [
    # Priority 1 — AI/ML (always shown first)
    {"code": "cs.AI", "name": "Artificial Intelligence", "priority": 1},
    {"code": "cs.LG", "name": "Machine Learning", "priority": 1},
    {"code": "cs.CL", "name": "NLP & Language Models", "priority": 1},
    {"code": "cs.CV", "name": "Computer Vision", "priority": 1},
    {"code": "stat.ML", "name": "Statistical ML", "priority": 1},

    # Priority 2 — Core Tech
    {"code": "cs.CR", "name": "Cybersecurity", "priority": 2},
    {"code": "cs.SE", "name": "Software Engineering", "priority": 2},
    {"code": "cs.DB", "name": "Databases", "priority": 2},
    {"code": "cs.DC", "name": "Distributed & Cloud Computing", "priority": 2},
    {"code": "cs.NI", "name": "Networking", "priority": 2},
    {"code": "cs.PL", "name": "Programming Languages", "priority": 2},
    {"code": "cs.OS", "name": "Operating Systems", "priority": 2},
    {"code": "cs.AR", "name": "Computer Architecture", "priority": 2},

    # Priority 3 — Cutting-edge & Trending
    {"code": "cs.RO", "name": "Robotics & AI", "priority": 3},
    {"code": "cs.MA", "name": "AI Agents & Multi-Agent Systems", "priority": 3},
    {"code": "cs.IR", "name": "Search & Recommendation AI", "priority": 3},
    {"code": "cs.MM", "name": "Multimodal AI", "priority": 3},
    {"code": "cs.HC", "name": "Human-AI Interaction", "priority": 3},
    {"code": "cs.SI", "name": "Social Networks & AI Ethics", "priority": 3},
    {"code": "cs.CY", "name": "AI & Society", "priority": 3},
]

ARXIV_RSS_BASE = "https://rss.arxiv.org/rss/{code}"


class ArxivCollector:
    """Fetches latest research papers from arXiv RSS feeds."""

    def __init__(self, max_papers_per_category: int = 10):
        self.max_per_cat = max_papers_per_category
        self.categories = ARXIV_CATEGORIES

    def fetch_all(self) -> Tuple[List[Dict], List[str]]:
        """Fetch papers from all 20 arXiv categories.

        Returns:
            (papers, failed_categories)
        """
        all_papers = []
        failed = []

        for cat in self.categories:
            try:
                papers = self._fetch_category(cat)
                all_papers.extend(papers)
            except Exception as e:
                logger.warning(f"arXiv fetch failed for {cat['code']}: {e}")
                failed.append(cat["code"])

        # Deduplicate by arxiv_id (papers can appear in multiple categories)
        seen_ids = set()
        unique_papers = []
        for paper in all_papers:
            if paper["arxiv_id"] not in seen_ids:
                seen_ids.add(paper["arxiv_id"])
                unique_papers.append(paper)

        arxiv_count = len(unique_papers)

        # Fetch from all secondary sources
        crossref_papers = self._fetch_crossref()
        semantic_papers = self._fetch_semantic_scholar()
        openalex_papers = self._fetch_openalex()

        # Deduplicate secondary sources by title
        seen_titles = {p["title"].lower().strip() for p in unique_papers}
        for paper in crossref_papers + semantic_papers + openalex_papers:
            title_key = paper["title"].lower().strip()
            if title_key not in seen_titles and paper["arxiv_id"] not in seen_ids:
                seen_titles.add(title_key)
                seen_ids.add(paper["arxiv_id"])
                unique_papers.append(paper)

        logger.info(
            f"Research: {len(unique_papers)} total papers "
            f"(arXiv: {arxiv_count}, Crossref: {len(crossref_papers)}, "
            f"Semantic Scholar: {len(semantic_papers)}, OpenAlex: {len(openalex_papers)})"
        )

        return unique_papers, failed

    # =============================================================
    # Crossref (free, no auth, no rate limits)
    # =============================================================

    def _fetch_crossref(self) -> List[Dict]:
        """Fetch papers from Crossref API (150M+ papers, free, reliable)."""
        import requests
        import re

        queries = [
            "generative AI large language models",
            "deep learning transformer neural network",
            "autonomous AI agents reinforcement",
            "machine learning optimization method",
            "multimodal AI computer vision language",
        ]

        papers = []
        seen_titles = set()

        for query in queries:
            try:
                resp = requests.get(
                    "https://api.crossref.org/works",
                    params={
                        "query": query,
                        "filter": "from-pub-date:2024-01-01",
                        "rows": 3,
                        "sort": "relevance",
                        "select": "DOI,title,author,abstract,published-print,published-online,URL",
                    },
                    headers={"User-Agent": "NewsIntelAgent/1.0 (mailto:research@newsintelagent.app)"},
                    timeout=15,
                )

                if resp.status_code != 200:
                    continue

                items = resp.json().get("message", {}).get("items", [])
                for item in items:
                    titles = item.get("title", [])
                    title = titles[0] if titles else ""
                    if not title or title.lower() in seen_titles:
                        continue
                    seen_titles.add(title.lower())

                    doi = item.get("DOI", "")
                    paper_id = f"cr-{doi.replace('/', '-')[:20]}" if doi else f"cr-{hash(title) % 100000:05d}"

                    authors = []
                    for a in item.get("author", [])[:10]:
                        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                        if name:
                            authors.append(name)

                    pub_parts = (
                        item.get("published-online", {}).get("date-parts", [[]])
                        or item.get("published-print", {}).get("date-parts", [[]])
                    )
                    if pub_parts and pub_parts[0]:
                        parts = pub_parts[0]
                        year = parts[0] if len(parts) > 0 else 2024
                        month = parts[1] if len(parts) > 1 else 1
                        day = parts[2] if len(parts) > 2 else 1
                        pub_date = f"{year}-{month:02d}-{day:02d}"
                    else:
                        pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    abstract = re.sub(r"<[^>]+>", "", item.get("abstract", "") or "").strip()

                    papers.append({
                        "arxiv_id": paper_id,
                        "title": title,
                        "abstract": abstract[:1000],
                        "authors": authors,
                        "published_at": f"{pub_date}T00:00:00+00:00",
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "pdf_url": f"https://doi.org/{doi}" if doi else "",
                        "abs_url": item.get("URL", f"https://doi.org/{doi}" if doi else ""),
                        "primary_category": "crossref",
                        "category_name": "Crossref",
                        "priority": 1,
                        "all_categories": ["Crossref"],
                    })

            except Exception as e:
                logger.debug(f"Crossref query failed: {e}")

        if papers:
            logger.info(f"Crossref: fetched {len(papers)} papers")
        return papers

    # =============================================================
    # Semantic Scholar (free, rate-limited ~1 req/sec)
    # =============================================================

    def _fetch_semantic_scholar(self) -> List[Dict]:
        """Fetch papers from Semantic Scholar API (200M+ papers)."""
        import requests
        import time

        queries = [
            "generative AI large language models",
            "autonomous AI agents",
            "multimodal foundation models",
        ]

        papers = []
        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(3)  # Respect rate limit

            try:
                for attempt in range(2):
                    resp = requests.get(
                        "https://api.semanticscholar.org/graph/v1/paper/search",
                        params={
                            "query": query,
                            "limit": 3,
                            "fields": "title,abstract,authors,year,externalIds,url,publicationDate",
                            "year": "2024-2025",
                        },
                        timeout=10,
                    )
                    if resp.status_code == 429:
                        time.sleep(5)
                        continue
                    break

                if resp.status_code != 200:
                    continue

                data = resp.json()
                for item in data.get("data", []):
                    title = item.get("title", "")
                    if not title:
                        continue

                    ext_ids = item.get("externalIds", {})
                    arxiv_id = ext_ids.get("ArXiv", "")
                    paper_id = f"s2-{item.get('paperId', '')[:12]}"

                    authors = [a.get("name", "") for a in item.get("authors", [])[:10]]
                    pub_date = item.get("publicationDate") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

                    papers.append({
                        "arxiv_id": paper_id,
                        "title": title,
                        "abstract": item.get("abstract", "") or "",
                        "authors": authors,
                        "published_at": f"{pub_date}T00:00:00+00:00",
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
                        "abs_url": item.get("url", ""),
                        "primary_category": "semantic",
                        "category_name": "Semantic Scholar",
                        "priority": 1,
                        "all_categories": ["Semantic Scholar"],
                    })

            except Exception as e:
                logger.debug(f"Semantic Scholar query failed: {e}")

        if papers:
            logger.info(f"Semantic Scholar: fetched {len(papers)} papers")
        return papers

    # =============================================================
    # OpenAlex (free, no auth, 250M+ papers)
    # =============================================================

    def _fetch_openalex(self) -> List[Dict]:
        """Fetch papers from OpenAlex API (250M+ works, free, generous limits)."""
        import requests

        queries = [
            "generative artificial intelligence",
            "large language model",
            "deep reinforcement learning",
        ]

        papers = []
        for query in queries:
            try:
                resp = requests.get(
                    "https://api.openalex.org/works",
                    params={
                        "search": query,
                        "filter": "from_publication_date:2024-01-01",
                        "sort": "cited_by_count:desc",
                        "per_page": 3,
                    },
                    headers={"User-Agent": "mailto:research@newsintelagent.app"},
                    timeout=15,
                )

                if resp.status_code != 200:
                    logger.debug(f"OpenAlex query failed ({resp.status_code})")
                    continue

                results = resp.json().get("results", [])
                for item in results:
                    title = item.get("title", "")
                    if not title:
                        continue

                    oa_id = item.get("id", "").split("/")[-1]
                    paper_id = f"oa-{oa_id[:15]}"

                    # Authors
                    authors = []
                    for a in item.get("authorships", [])[:10]:
                        name = a.get("author", {}).get("display_name", "")
                        if name:
                            authors.append(name)

                    pub_date = item.get("publication_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

                    # Best available URL
                    doi = item.get("doi", "") or ""
                    pdf_url = ""
                    if item.get("open_access", {}).get("oa_url"):
                        pdf_url = item["open_access"]["oa_url"]
                    elif doi:
                        pdf_url = doi

                    papers.append({
                        "arxiv_id": paper_id,
                        "title": title,
                        "abstract": "",  # OpenAlex doesn't return abstracts in search
                        "authors": authors,
                        "published_at": f"{pub_date}T00:00:00+00:00",
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "pdf_url": pdf_url,
                        "abs_url": doi or item.get("id", ""),
                        "primary_category": "openalex",
                        "category_name": "OpenAlex",
                        "priority": 1,
                        "all_categories": ["OpenAlex"],
                    })

            except Exception as e:
                logger.debug(f"OpenAlex query failed: {e}")

        if papers:
            logger.info(f"OpenAlex: fetched {len(papers)} papers")
        return papers

    def _fetch_category(self, category: Dict) -> List[Dict]:
        """Fetch papers from a single arXiv category RSS feed.

        Args:
            category: Dict with code, name, priority.

        Returns:
            List of paper dicts.
        """
        url = ARXIV_RSS_BASE.format(code=category["code"])
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            raise Exception(f"Feed parse error: {feed.bozo_exception}")

        papers = []
        for entry in feed.entries[:self.max_per_cat]:
            paper = self._parse_entry(entry, category)
            if paper:
                papers.append(paper)

        if papers:
            logger.debug(f"  arXiv {category['code']}: {len(papers)} papers")

        return papers

    def _parse_entry(self, entry, category: Dict) -> Dict:
        """Parse a single RSS entry into a paper dict.

        Args:
            entry: feedparser entry.
            category: Category metadata.

        Returns:
            Paper dict or None if unparseable.
        """
        try:
            # Extract arXiv ID from the link
            link = entry.get("link", "")
            arxiv_id = self._extract_arxiv_id(link)

            title = entry.get("title", "").strip()
            # arXiv titles sometimes have "(arXiv:XXXX.XXXXX ...)" appended
            title = re.sub(r"\s*\(arXiv:[\d.]+v\d+.*?\)\s*$", "", title)
            title = re.sub(r"\s+", " ", title).strip()

            if not title or not arxiv_id:
                return None

            # Parse abstract/description
            abstract = entry.get("summary", entry.get("description", ""))
            # Clean HTML tags from abstract
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()
            # Truncate very long abstracts
            if len(abstract) > 2000:
                abstract = abstract[:1997] + "..."

            # Parse authors
            authors = []
            if hasattr(entry, "authors"):
                authors = [a.get("name", "") for a in entry.authors if a.get("name")]
            elif hasattr(entry, "author"):
                authors = [entry.author]

            # Parse date
            published = entry.get("published", entry.get("updated", ""))
            try:
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published = pub_dt.isoformat()
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                    published = pub_dt.isoformat()
            except Exception:
                published = datetime.now(timezone.utc).isoformat()

            # Extract all categories/tags
            tags = []
            if hasattr(entry, "tags"):
                tags = [t.get("term", "") for t in entry.tags if t.get("term")]

            return {
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": abstract,
                "authors": authors[:10],  # Cap at 10 authors
                "published_at": published,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
                "abs_url": f"https://arxiv.org/abs/{arxiv_id}",
                "primary_category": category["code"],
                "category_name": category["name"],
                "priority": category["priority"],
                "all_categories": tags or [category["code"]],
            }

        except Exception as e:
            logger.debug(f"Failed to parse arXiv entry: {e}")
            return None

    def _extract_arxiv_id(self, url: str) -> str:
        """Extract arXiv paper ID from URL.

        Examples:
            'http://arxiv.org/abs/2401.12345' -> '2401.12345'
            'http://arxiv.org/abs/2401.12345v2' -> '2401.12345'
        """
        match = re.search(r"(\d{4}\.\d{4,5})", url)
        if match:
            return match.group(1)
        return ""
