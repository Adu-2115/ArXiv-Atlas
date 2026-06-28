"""
MMR (Maximal Marginal Relevance) diversity reranking.

Cross-encoder + LLM scoring both reward textual similarity to the topic,
which can produce a final set of papers that are all near-duplicates of the
same phrasing/angle on the topic. MMR re-orders the ranked list to balance
relevance against diversity from papers already picked, so "take the top N"
downstream gets a set that actually spans different sub-approaches.
"""
from functools import lru_cache
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import get_settings
from app.models.schemas import RankedPaper

settings = get_settings()


@lru_cache
def _get_embedder() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def mmr_rerank(papers: list[RankedPaper], lambda_param: float | None = None) -> list[RankedPaper]:
    """
    Reorders `papers` by MMR: greedily picks the paper maximizing
    lambda * relevance - (1 - lambda) * max_similarity_to_already_selected.

    Returns the same papers in a new order (relevance+diversity balanced),
    so downstream "take the top N" logic benefits without changing what
    pool of papers is available.
    """
    if len(papers) <= 2:
        return papers

    lam = lambda_param if lambda_param is not None else settings.mmr_lambda

    model = _get_embedder()
    texts = [f"{p.title}. {p.abstract[:300]}" for p in papers]
    embeddings = np.array(model.encode(texts, normalize_embeddings=True))

    relevance = np.array(
        [
            p.final_score
            if p.final_score is not None
            else (p.llm_relevance_score if p.llm_relevance_score is not None else p.cross_encoder_score)
            for p in papers
        ],
        dtype=float,
    )
    # Normalize to 0-1 so it's comparable to cosine similarity in the blend.
    if relevance.max() > relevance.min():
        relevance = (relevance - relevance.min()) / (relevance.max() - relevance.min())

    selected_idx: list[int] = []
    remaining_idx = list(range(len(papers)))

    first = int(np.argmax(relevance))
    selected_idx.append(first)
    remaining_idx.remove(first)

    while remaining_idx:
        best_idx = None
        best_score = -float("inf")
        for idx in remaining_idx:
            sim_to_selected = max(
                float(np.dot(embeddings[idx], embeddings[s])) for s in selected_idx
            )
            mmr_score = lam * relevance[idx] - (1 - lam) * sim_to_selected
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx
        selected_idx.append(best_idx)
        remaining_idx.remove(best_idx)

    return [papers[i] for i in selected_idx]
