"""
Shared Pydantic models for the research pipeline.
These are the contracts between pipeline stages AND the API response shape
consumed by the Next.js frontend (graph view).
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ---------- Stage 1: arxiv search ----------

class ArxivPaper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str] = Field(default_factory=list)
    published: str | None = None          # ISO date string
    pdf_url: str | None = None
    ar5iv_url: str | None = None
    primary_category: str | None = None


# ---------- Stage 2: ranking ----------

class RankedPaper(ArxivPaper):
    cross_encoder_score: float
    llm_relevance_score: float | None = None
    llm_justification: str | None = None


# ---------- Stage 3: extraction ----------

class PaperInsights(BaseModel):
    arxiv_id: str
    title: str
    problem: str
    method: str
    key_results: list[str] = Field(default_factory=list)
    datasets_benchmarks: list[str] = Field(default_factory=list)
    limitations: str | None = None


# ---------- Stage 4: research map (graph) ----------

class GraphNode(BaseModel):
    id: str                      # arxiv_id
    title: str
    cluster_id: str
    summary: str
    relevance_score: float | None = None
    year: str | None = None


class GraphCluster(BaseModel):
    id: str
    label: str
    description: str


RelationType = Literal[
    "builds_on", "contradicts", "shares_method", "shares_dataset", "related"
]


class GraphEdge(BaseModel):
    source: str
    target: str
    relation_type: RelationType
    label: str


class ResearchMap(BaseModel):
    topic: str
    clusters: list[GraphCluster]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    open_problems: list[str] = Field(default_factory=list)
    overview: str


# ---------- Full pipeline response ----------

class PipelineResult(BaseModel):
    topic: str
    candidates_found: int
    ranked_papers: list[RankedPaper]
    insights: list[PaperInsights]
    research_map: ResearchMap


class TopicRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
