"""
Research paper analyzer for the News Intelligence Agent.

Uses Gemini to analyze arXiv paper abstracts and extract:
- Summary of the research
- Problems/challenges the paper addresses
- Open problems and opportunities for contribution
- Difficulty level and required skills
"""

import json
from typing import List, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class ResearchAnalyzer:
    """Analyzes research papers using Gemini AI."""

    def __init__(self, gemini_client=None):
        self.gemini = gemini_client

    def analyze_papers(self, papers: List[Dict]) -> List[Dict]:
        """Analyze a batch of papers with Gemini.

        For each paper, extracts structured insights from the abstract.
        Falls back to heuristic analysis if Gemini is unavailable.

        Args:
            papers: List of paper dicts from ArxivCollector.

        Returns:
            Same list with 'analysis' field added to each paper.
        """
        if not papers:
            return papers

        analyzed = 0
        for paper in papers:
            # Skip already analyzed papers
            if paper.get("analysis") and paper["analysis"].get("summary"):
                continue

            try:
                analysis = self._analyze_single(paper)
                paper["analysis"] = analysis
                analyzed += 1
            except Exception as e:
                logger.debug(f"Analysis failed for {paper.get('arxiv_id', '?')}: {e}")
                paper["analysis"] = self._fallback_analysis(paper)

        logger.info(f"Research analyzer: analyzed {analyzed}/{len(papers)} papers")
        return papers

    def _analyze_single(self, paper: Dict) -> Dict:
        """Analyze a single paper using Gemini.

        Args:
            paper: Paper dict with title and abstract.

        Returns:
            Analysis dict with structured insights.
        """
        if not self.gemini:
            return self._fallback_analysis(paper)

        prompt = self._build_prompt(paper)

        try:
            from config.settings import GEMINI_MODEL, GEMINI_TEMPERATURE
            import google.generativeai as genai

            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=GEMINI_TEMPERATURE,
                    max_output_tokens=800,
                ),
            )

            text = response.text.strip()
            # Try to parse JSON from the response
            analysis = self._parse_json_response(text)
            if analysis:
                return analysis

        except Exception as e:
            logger.debug(f"Gemini analysis error: {e}")

        return self._fallback_analysis(paper)

    def _build_prompt(self, paper: Dict) -> str:
        """Build the analysis prompt for Gemini."""
        title = paper.get("title", "Unknown")
        abstract = paper.get("abstract", "")[:1500]
        category = paper.get("category_name", "Computer Science")

        return f"""Analyze this research paper and return a JSON object.

Title: {title}
Category: {category}
Abstract: {abstract}

Return ONLY valid JSON with these fields:
{{
    "summary": "2-3 sentence plain-English summary of what this paper does",
    "problem_addressed": "The specific problem or challenge this paper tackles",
    "key_finding": "The main result or contribution in one sentence",
    "open_problems": ["List of 1-3 open problems or limitations mentioned"],
    "opportunities": ["1-3 ways someone could build on this work or contribute"],
    "difficulty": "beginner|intermediate|advanced",
    "skills_needed": ["2-4 specific skills needed to work on this"],
    "field_tags": ["2-3 specific subfield tags like 'LLM', 'reinforcement learning', 'computer vision'"]
}}

Be specific and practical in the opportunities — focus on what a developer/researcher could actually do."""

    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """Try to parse JSON from Gemini response.

        Handles cases where the model wraps JSON in markdown code blocks.
        """
        # Strip markdown code fences
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (```json and ```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
            # Validate required fields
            if isinstance(data, dict) and "summary" in data:
                return {
                    "summary": str(data.get("summary", "")),
                    "problem_addressed": str(data.get("problem_addressed", "")),
                    "key_finding": str(data.get("key_finding", "")),
                    "open_problems": list(data.get("open_problems", [])),
                    "opportunities": list(data.get("opportunities", [])),
                    "difficulty": str(data.get("difficulty", "intermediate")),
                    "skills_needed": list(data.get("skills_needed", [])),
                    "field_tags": list(data.get("field_tags", [])),
                }
        except json.JSONDecodeError:
            pass

        return None

    def _fallback_analysis(self, paper: Dict) -> Dict:
        """Generate a basic analysis without AI.

        Uses simple heuristics on the abstract text.
        """
        abstract = paper.get("abstract", "").lower()
        title = paper.get("title", "").lower()
        category = paper.get("category_name", "Computer Science")

        # Extract a simple summary (first sentence of abstract)
        first_sentence = paper.get("abstract", "")
        if ". " in first_sentence:
            first_sentence = first_sentence.split(". ")[0] + "."
        if len(first_sentence) > 200:
            first_sentence = first_sentence[:197] + "..."

        # Detect difficulty from keywords
        difficulty = "intermediate"
        advanced_kw = ["theorem", "proof", "convergence", "theoretical", "asymptotic"]
        beginner_kw = ["survey", "tutorial", "introduction", "overview", "benchmark"]
        if any(kw in abstract for kw in advanced_kw):
            difficulty = "advanced"
        elif any(kw in abstract for kw in beginner_kw):
            difficulty = "beginner"

        # Detect field tags from content
        field_tags = []
        tag_keywords = {
            "LLM": ["language model", "llm", "gpt", "transformer"],
            "Computer Vision": ["image", "visual", "detection", "segmentation"],
            "Reinforcement Learning": ["reinforcement", "reward", "policy", "agent"],
            "NLP": ["text", "sentiment", "translation", "nlp"],
            "Generative AI": ["diffusion", "generative", "gan", "generation"],
            "Robotics": ["robot", "manipulation", "navigation"],
            "Security": ["attack", "vulnerability", "privacy", "adversarial"],
            "Optimization": ["optimization", "gradient", "convergence"],
            "Data Science": ["data", "analytics", "feature", "dataset"],
            "Graph ML": ["graph", "node", "edge", "network"],
        }
        for tag, keywords in tag_keywords.items():
            if any(kw in abstract or kw in title for kw in keywords):
                field_tags.append(tag)

        return {
            "summary": first_sentence,
            "problem_addressed": f"Research in {category}",
            "key_finding": "See abstract for details.",
            "open_problems": ["Refer to the full paper for open questions."],
            "opportunities": [
                "Reproduce and validate the results",
                "Extend the approach to new domains",
                "Combine with other recent methods",
            ],
            "difficulty": difficulty,
            "skills_needed": ["Python", "Research methodology"],
            "field_tags": field_tags[:3] if field_tags else [category],
        }
