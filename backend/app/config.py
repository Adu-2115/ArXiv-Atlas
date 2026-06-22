"""
Centralized configuration, loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"          # general purpose reasoning model
    groq_extraction_model: str = "llama-3.3-70b-versatile"

    # Pipeline tuning
    max_candidates: int = 60            # papers pulled from arxiv before reranking
    max_query_expansions: int = 4        # alternate search queries generated from the topic
    cross_encoder_top_k: int = 20        # survivors after cross-encoder stage
    final_paper_count: int = 12          # survivors after LLM relevance stage
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # CORS
    frontend_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
