"""
Stage 1: Find papers.

arxiv's search API is keyword-based, not semantic, so a single raw query
misses a lot of relevant work. We ask the LLM to expand the topic into a
handful of alternate search queries (synonyms / subtopics / related terms),
run them all against arxiv, and deduplicate by arxiv_id.
"""
import arxiv
from app.config import get_settings
from app.models.schemas import ArxivPaper
from app.services.cache import ONE_WEEK, cache_get, cache_set
from app.services.groq_client import chat_json

settings = get_settings()
_client = arxiv.Client()


def expand_queries(topic: str) -> list[str]:
    """Ask the LLM for alternate arxiv search queries for this topic."""
    cache_key = f"query_expansion:v1:{topic.strip().lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    system = (
        "You generate effective arxiv.org search queries. arxiv search is "
        "keyword-based, so queries should use precise technical terminology, "
        "synonyms, and related subtopics — not natural language questions."
    )
    user = (
        f'Topic: "{topic}"\n\n'
        f"Generate {settings.max_query_expansions} distinct arxiv search queries "
        "that together would surface the most relevant papers on this topic. "
        'Return JSON: {"queries": ["query1", "query2", ...]}'
    )
    try:
        result = chat_json(system, user)
        queries = result.get("queries", [])
        if not queries:
            queries = [topic]
        else:
            queries = queries[: settings.max_query_expansions]
    except Exception:
        # Fall back to the raw topic if the LLM call fails for any reason.
        queries = [topic]

    cache_set(cache_key, queries, ttl_seconds=ONE_WEEK)
    return queries


def _to_arxiv_paper(result: arxiv.Result) -> ArxivPaper:
    arxiv_id = result.get_short_id().split("v")[0]  # strip version suffix
    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=result.title.strip().replace("\n", " "),
        abstract=result.summary.strip().replace("\n", " "),
        authors=[a.name for a in result.authors],
        published=result.published.isoformat() if result.published else None,
        pdf_url=result.pdf_url,
        ar5iv_url=f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}",
        primary_category=result.primary_category,
    )


def search_arxiv(queries: list[str], per_query_limit: int = 25) -> list[ArxivPaper]:
    """Run multiple queries against arxiv and dedupe results by arxiv_id."""
    seen: dict[str, ArxivPaper] = {}
    for q in queries:
        search = arxiv.Search(
            query=q,
            max_results=per_query_limit,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        try:
            for result in _client.results(search):
                paper = _to_arxiv_paper(result)
                if paper.arxiv_id not in seen:
                    seen[paper.arxiv_id] = paper
        except Exception:
            # One bad query shouldn't kill the whole search stage.
            continue

    papers = list(seen.values())
    return papers[: get_settings().max_candidates]


def find_papers(topic: str) -> list[ArxivPaper]:
    queries = expand_queries(topic)
    return search_arxiv(queries)
