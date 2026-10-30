"""Responses API orchestration for the campus assistant."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Iterable

from .config import Settings
from .db import CampusDatabase
from .prompts import (
    NO_DATA_REPLY,
    OUT_OF_SCOPE_REPLY,
    PROMPT_LEAK_REPLY,
    SYSTEM_PROMPT,
    is_prompt_attack,
)
from .rag import OpenAIEmbeddingProvider, RuleRetriever
from .tools import TOOLS, ToolRegistry


class CampusAssistant:
    """High-level application service used by the Gradio UI and tests."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
        database: CampusDatabase | None = None,
        retriever: RuleRetriever | None = None,
    ):
        self.settings = settings or Settings.from_env()
        if client is None:
            if not self.settings.api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not configured. Add it to the approved local env file."
                )
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("Install the packages in requirements.txt first.") from exc
            client = OpenAI(api_key=self.settings.api_key)
        self.client = client
        self.database = database or CampusDatabase(self.settings.db_path)
        self.retriever = retriever or RuleRetriever(
            rules_path=self.settings.rules_path,
            cache_path=self.settings.rag_cache_path,
            provider=OpenAIEmbeddingProvider(self.client, self.settings.embedding_model),
            model=self.settings.embedding_model,
        )
        self.registry = ToolRegistry(self.database, self.retriever)

    @staticmethod
    def _history_items(history: Iterable[Any] | None) -> list[dict[str, str]]:
        if not history:
            return []
        items: list[dict[str, str]] = []
        for entry in list(history)[-12:]:
            if isinstance(entry, dict) and entry.get("role") in {"user", "assistant"}:
                content = entry.get("content")
                if isinstance(content, str) and content.strip():
                    items.append({"role": entry["role"], "content": content})
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                user_text, assistant_text = entry
                if isinstance(user_text, str) and user_text.strip():
                    items.append({"role": "user", "content": user_text})
                if isinstance(assistant_text, str) and assistant_text.strip():
                    items.append({"role": "assistant", "content": assistant_text})
        return items

    @staticmethod
    def _function_calls(output: Iterable[Any]) -> list[Any]:
        return [item for item in output if getattr(item, "type", None) == "function_call"]

    def chat(self, message: str, history: Iterable[Any] | None = None) -> str:
        message = (message or "").strip()
        if not message:
            return "請輸入你想查詢或辦理的校園空間預約問題。"
        if is_prompt_attack(message):
            return PROMPT_LEAK_REPLY

        input_items: list[Any] = self._history_items(history)
        input_items.append({"role": "user", "content": message})
        missing_record_seen = False

        for _ in range(self.settings.max_tool_rounds):
            response = self.client.responses.create(
                model=self.settings.model,
                instructions=(
                    f"{SYSTEM_PROMPT}\n\n"
                    f"今天日期是 {date.today().isoformat()}（Asia/Taipei）。"
                    "使用者說『今天』或『明天』時，先換算為 YYYY-MM-DD 再呼叫工具。"
                ),
                tools=TOOLS,
                input=input_items,
                store=False,
            )
            output = list(getattr(response, "output", []) or [])
            input_items.extend(output)
            calls = self._function_calls(output)
            if not calls:
                answer = (getattr(response, "output_text", "") or "").strip()
                if missing_record_seen:
                    return NO_DATA_REPLY
                return answer or OUT_OF_SCOPE_REPLY

            for call in calls:
                result = self.registry.execute(call.name, call.arguments)
                if call.name in {"get_booking", "cancel_booking"} and result.get("found") is False:
                    missing_record_seen = True
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

        return "目前無法完成這個操作，請縮短問題或稍後再試。"

    def reset_demo_data(self) -> None:
        self.database.reset()

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "api_key_configured": self.settings.has_api_key,
            "model": self.settings.model,
            "embedding_model": self.settings.embedding_model,
            "database": str(self.database.path),
            "rule_sections": len(self.retriever.chunks),
        }
