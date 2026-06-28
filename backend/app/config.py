"""
Centralized configuration, loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Groq
    groq_api_key: str = ""
    # Reasoning-heavy stages (relative judgment across many papers, finding
    # cross-paper relationships) use the larger model.
    groq_model: str = "llama-3.3-70b-versatile"
    # Narrow, single-paper-at-a-time tasks use a much cheaper/faster model —
    # query expansion and per-paper extraction don't need 70B-level reasoning,
    # and extraction in particular runs once per paper, so this is where most
    # of your token cost comes from.
    groq_query_expansion_model: str = "llama-3.1-8b-instant"
    groq_extraction_model: str = "llama-3.1-8b-instant"

    # Pipeline tuning
    max_candidates: int = 60            # papers pulled from arxiv before reranking
    max_query_expansions: int = 4        # alternate search queries generated from the topic
    cross_encoder_top_k: int = 15        # survivors after cross-encoder stage
    final_paper_count: int = 12          # survivors after LLM relevance stage
    min_relevance_score: float = 40.0    # papers below this score are excluded entirely,
                                          # even if it means returning fewer than final_paper_count
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Final ranking score blend: relevance (LLM judgment) + citation count
    # (Semantic Scholar, normalized) + recency (newer = higher, normalized).
    # Weights must sum to 1.0 for the blend to stay in a comparable 0-1 range.
    relevance_weight: float = 0.55
    citation_weight: float = 0.3
    recency_weight: float = 0.15

    # MMR diversity reranking — balances relevance against similarity to
    # already-selected papers, so the final set spans different
    # sub-approaches instead of clustering around one phrasing of the topic.
    # 1.0 = pure relevance (no diversity effect), lower = more diversity.
    mmr_lambda: float = 0.7
    embedding_model: str = "all-MiniLM-L6-v2"

    # CORS
    frontend_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
