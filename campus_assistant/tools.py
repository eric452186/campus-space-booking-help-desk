"""Tool schemas and trusted application-side tool execution."""

from __future__ import annotations

import json
from typing import Any

from .db import BookingError, CampusDatabase
from .rag import RuleRetriever


TOOLS = [
    {
        "type": "function",
        "name": "list_available_rooms",
        "description": "查詢指定日期、時段與最低容納人數可預約的校園空間。",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_date": {"type": "string", "description": "YYYY-MM-DD"},
                "start_time": {"type": "string", "description": "24 小時制 HH:MM"},
                "end_time": {"type": "string", "description": "24 小時制 HH:MM"},
                "min_capacity": {"type": "integer", "minimum": 1},
            },
            "required": ["booking_date", "start_time", "end_time", "min_capacity"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "create_booking",
        "description": "在使用者已確認完整資料後，建立一筆校園空間預約。",
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "booking_date": {"type": "string", "description": "YYYY-MM-DD"},
                "start_time": {"type": "string", "description": "24 小時制 HH:MM"},
                "end_time": {"type": "string", "description": "24 小時制 HH:MM"},
                "purpose": {"type": "string"},
            },
            "required": ["room_id", "booking_date", "start_time", "end_time", "purpose"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_booking",
        "description": "依預約編號查詢預約狀態與詳細資料。",
        "parameters": {
            "type": "object",
            "properties": {"booking_id": {"type": "string"}},
            "required": ["booking_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "cancel_booking",
        "description": "依預約編號取消一筆存在的預約。",
        "parameters": {
            "type": "object",
            "properties": {"booking_id": {"type": "string"}},
            "required": ["booking_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_campus_rules",
        "description": "以 RAG 搜尋校園空間的開放、預約、取消、飲食與安全規章。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["query", "top_k"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


class ToolRegistry:
    def __init__(self, database: CampusDatabase, retriever: RuleRetriever):
        self.database = database
        self.retriever = retriever

    def execute(self, name: str, arguments_json: str) -> dict[str, Any]:
        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError:
            return {"ok": False, "error": "工具參數不是有效 JSON。"}

        try:
            if name == "list_available_rooms":
                rooms = self.database.list_available_rooms(**arguments)
                return {"ok": True, "count": len(rooms), "rooms": rooms}
            if name == "create_booking":
                return {"ok": True, "booking": self.database.create_booking(**arguments)}
            if name == "get_booking":
                booking = self.database.get_booking(**arguments)
                return {"ok": True, "found": booking is not None, "booking": booking}
            if name == "cancel_booking":
                booking = self.database.cancel_booking(**arguments)
                return {"ok": True, "found": booking is not None, "booking": booking}
            if name == "search_campus_rules":
                results = self.retriever.search(**arguments)
                return {"ok": True, "count": len(results), "results": results}
            return {"ok": False, "error": f"不支援的工具：{name}"}
        except (BookingError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
