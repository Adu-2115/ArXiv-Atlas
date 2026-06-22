"""
Stage 4: Map research.

Takes structured extractions (not raw papers — cheaper and more controllable)
and asks the LLM to produce a graph: clusters of related papers, an overview
narrative, open problems, and edges describing relationships between papers
(builds_on / contradicts / shares_method / shares_dataset / related).

This JSON is consumed directly by the frontend's force-directed graph view.
"""
from app.models.schemas import GraphCluster, GraphEdge, GraphNode, PaperInsights, RankedPaper, ResearchMap
from app.services.cache import ONE_DAY, cache_get, cache_set
from app.services.groq_client import chat_json

_SYNTHESIS_SYSTEM = (
    "You are a research analyst building a visual map of a research "
    "landscape. You group papers into thematic clusters, identify how "
    "papers relate to each other (building on, contradicting, sharing "
    "methods/datasets), and surface open problems. Be specific and ground "
    "every claim in the provided paper summaries — do not invent papers or "
    "relationships not supported by the text."
)


def _build_paper_block(paper: RankedPaper, insight: PaperInsights) -> str:
    year = (paper.published or "")[:4]
    return (
        f"arxiv_id: {paper.arxiv_id}\n"
        f"title: {paper.title}\n"
        f"year: {year}\n"
        f"problem: {insight.problem}\n"
        f"method: {insight.method}\n"
        f"datasets: {', '.join(insight.datasets_benchmarks) or 'none listed'}\n"
    )


def build_research_map(
    topic: str, papers: list[RankedPaper], insights: list[PaperInsights]
) -> ResearchMap:
    insight_by_id = {i.arxiv_id: i for i in insights}
    blocks = "\n---\n".join(
        _build_paper_block(p, insight_by_id[p.arxiv_id])
        for p in papers
        if p.arxiv_id in insight_by_id
    )

    user = (
        f'Topic: "{topic}"\n\n'
        f"Papers:\n{blocks}\n\n"
        "Build a research map as JSON with this exact shape:\n"
        "{\n"
        '  "overview": "2-4 sentence narrative summary of the research landscape",\n'
        '  "clusters": [{"id": "c1", "label": "short cluster name", "description": "1 sentence"}],\n'
        '  "nodes": [{"id": "<arxiv_id>", "title": "...", "cluster_id": "c1", '
        '"summary": "1 sentence on this paper\'s contribution", "year": "2023"}],\n'
        '  "edges": [{"source": "<arxiv_id>", "target": "<arxiv_id>", '
        '"relation_type": "builds_on|contradicts|shares_method|shares_dataset|related", '
        '"label": "short phrase describing the relationship"}],\n'
        '  "open_problems": ["open problem 1", "open problem 2"]\n'
        "}\n\n"
        "Every paper's arxiv_id must appear as exactly one node. Use only "
        "arxiv_ids from the list above in nodes and edges. Aim for 2-5 "
        "clusters and at least one edge per paper where a real relationship exists."
    )

    paper_ids = sorted(p.arxiv_id for p in papers if p.arxiv_id in insight_by_id)
    cache_key = f"research_map:v1:{topic.strip().lower()}:{','.join(paper_ids)}"
    cached = cache_get(cache_key)

    if cached is None:
        try:
            data = chat_json(_SYNTHESIS_SYSTEM, user, max_tokens=4096, temperature=0.3)
            cache_set(cache_key, data, ttl_seconds=ONE_DAY)
        except Exception as e:
            # Don't crash the whole pipeline if synthesis fails (e.g. rate
            # limit / quota exhausted) — return a minimal map with the
            # papers as standalone nodes and no clustering, plus a clear
            # message instead of an opaque 500/SSE crash.
            return ResearchMap(
                topic=topic,
                clusters=[],
                nodes=[
                    GraphNode(
                        id=p.arxiv_id,
                        title=p.title,
                        cluster_id="unclustered",
                        summary=insight_by_id[p.arxiv_id].method
                        if p.arxiv_id in insight_by_id
                        else "",
                        year=(p.published or "")[:4],
                    )
                    for p in papers
                    if p.arxiv_id in insight_by_id
                ],
                edges=[],
                open_problems=[],
                overview=(
                    "Research map generation failed (likely a temporary LLM "
                    f"provider issue: {e}). Papers and insights below are "
                    "still valid — try again shortly to regenerate the map."
                ),
            )
    else:
        data = cached

    clusters = [GraphCluster(**c) for c in data.get("clusters", [])]
    nodes = [GraphNode(**n) for n in data.get("nodes", [])]
    edges = [GraphEdge(**e) for e in data.get("edges", []) if e.get("source") != e.get("target")]

    return ResearchMap(
        topic=topic,
        clusters=clusters,
        nodes=nodes,
        edges=edges,
        open_problems=data.get("open_problems", []),
        overview=data.get("overview", ""),
    )
