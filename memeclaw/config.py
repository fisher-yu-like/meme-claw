"""MemeClaw configuration — all tunables in one place."""

import os
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Config:
    # LLM — OpenAI-compatible API
    llm_api_key: str = os.getenv("OPENAI_API_KEY", "sk-xxx")
    llm_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    llm_model: str = os.getenv("MEMECLAW_LLM_MODEL", "deepseek-v4-pro")
    llm_max_tokens: int = 4096
    long_context_model: str = os.getenv("MEMECLAW_LONG_CTX_MODEL", "deepseek-v4-pro")
    long_context_max_tokens: int = 3200

    # Search
    search_api: str = os.getenv("SEARCH_API", "serpapi")  # duckduckgo | google | serpapi
    serpapi_key: Optional[str] = os.getenv("SERPAPI_KEY")

    # Video platforms
    video_sources: list = field(default_factory=lambda: ["bilibili", "douyin", "youtube"])

    # Storage
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name: str = "memeclaw"
    vector_db_path: str = os.getenv("VECTOR_DB_PATH", "./data/vector_store")

    # Intelligence
    cron_scan_hour: int = 0  # 3 AM daily scan
    hot_threshold_ratio: float = 2.0  # 200% spike = new meme (legacy)
    hot_score_threshold: int = 60  # Minimum LLM hot_score to qualify as hot meme
    max_search_results: int = 8  # Results per platform query

    # Output
    export_dir: str = os.getenv("MEMECLAW_EXPORT_DIR", "./data/reports")


config = Config()
