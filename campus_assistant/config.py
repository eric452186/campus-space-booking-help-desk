"""Configuration helpers that never expose credential values."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_env_files() -> None:
    """Load developer-only settings without overriding process variables."""

    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PROJECT_ROOT / ".env.local", override=False)
    load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    db_path: Path = PROJECT_ROOT / "data" / "campus_demo.db"
    rules_path: Path = PROJECT_ROOT / "data" / "campus_rules.md"
    rag_cache_path: Path = PROJECT_ROOT / "data" / ".rag_index.json"
    max_tool_rounds: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        _load_env_files()
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
            ).strip(),
            db_path=Path(os.getenv("CAMPUS_DB_PATH", PROJECT_ROOT / "data" / "campus_demo.db")),
            rules_path=Path(
                os.getenv("CAMPUS_RULES_PATH", PROJECT_ROOT / "data" / "campus_rules.md")
            ),
            rag_cache_path=Path(
                os.getenv("CAMPUS_RAG_CACHE_PATH", PROJECT_ROOT / "data" / ".rag_index.json")
            ),
            max_tool_rounds=max(1, int(os.getenv("MAX_TOOL_ROUNDS", "5"))),
        )

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)
