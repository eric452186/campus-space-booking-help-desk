"""SQLite storage for synthetic campus rooms and reservations."""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator


SEED_ROOMS = (
    ("LIB-201", "圖書館二樓討論室", 6, "白板、螢幕"),
    ("LIB-305", "圖書館三樓安靜討論室", 4, "白板"),
    ("ENG-A101", "工程館 A101 共創教室", 24, "投影機、白板、可移動桌椅"),
    ("ACT-102", "學生活動中心 102", 40, "投影機、音響"),
)


class BookingError(ValueError):
    """Raised when a booking violates data or availability rules."""


class CampusDatabase:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS rooms (
                    room_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    capacity INTEGER NOT NULL CHECK (capacity > 0),
                    equipment TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bookings (
                    booking_id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL REFERENCES rooms(room_id),
                    booking_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    requester_id TEXT NOT NULL DEFAULT 'DEMO-STUDENT',
                    status TEXT NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed', 'cancelled')),
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO rooms(room_id, name, capacity, equipment)
                VALUES (?, ?, ?, ?)
                """,
                SEED_ROOMS,
            )
            connection.commit()

    def reset(self) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM bookings")
            connection.commit()

    @staticmethod
    def _validate_date(value: str) -> str:
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise BookingError("日期必須使用 YYYY-MM-DD 格式。") from exc
        if parsed < date.today():
            raise BookingError("不能預約過去的日期。")
        return parsed.isoformat()

    @staticmethod
    def _validate_time(value: str) -> str:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise BookingError("時間必須使用 24 小時制 HH:MM 格式。")
        return value

    @staticmethod
    def _minutes(value: str) -> int:
        hours, minutes = (int(part) for part in value.split(":"))
        return hours * 60 + minutes

    @classmethod
    def _is_room_open(
        cls, room_id: str, booking_date: str, start_time: str, end_time: str
    ) -> bool:
        weekday = date.fromisoformat(booking_date).weekday()
        start = cls._minutes(start_time)
        end = cls._minutes(end_time)
        if room_id.startswith("LIB-"):
            opening, closing = ((8 * 60 + 30, 21 * 60) if weekday < 5 else (9 * 60, 17 * 60))
        elif room_id.startswith("ENG-"):
            if weekday >= 5:
                return False
            opening, closing = 9 * 60, 20 * 60
        else:
            opening, closing = 9 * 60, 21 * 60 + 30
        return opening <= start < end <= closing

    @classmethod
    def _validate_slot_rules(
        cls, room_id: str, booking_date: str, start_time: str, end_time: str
    ) -> None:
        parsed_date = date.fromisoformat(booking_date)
        if parsed_date > date.today() + timedelta(days=30):
            raise BookingError("最早只能預約未來 30 天內的日期。")
        start = cls._minutes(start_time)
        end = cls._minutes(end_time)
        if start >= end:
            raise BookingError("結束時間必須晚於開始時間。")
        if start % 30 or end % 30:
            raise BookingError("預約時間必須以 30 分鐘為單位。")
        if end - start > 180:
            raise BookingError("單次預約最長 3 小時。")
        if not cls._is_room_open(room_id, booking_date, start_time, end_time):
            raise BookingError("指定時段不在該空間的開放時間內。")

    def list_available_rooms(
        self,
        booking_date: str,
        start_time: str,
        end_time: str,
        min_capacity: int = 1,
    ) -> list[dict[str, Any]]:
        booking_date = self._validate_date(booking_date)
        start_time = self._validate_time(start_time)
        end_time = self._validate_time(end_time)
        if start_time >= end_time:
            raise BookingError("結束時間必須晚於開始時間。")
        if min_capacity < 1:
            raise BookingError("容納人數至少為 1。")

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT r.room_id, r.name, r.capacity, r.equipment
                FROM rooms AS r
                WHERE r.capacity >= ?
                  AND NOT EXISTS (
                    SELECT 1 FROM bookings AS b
                    WHERE b.room_id = r.room_id
                      AND b.booking_date = ?
                      AND b.status = 'confirmed'
                      AND b.start_time < ?
                      AND b.end_time > ?
                  )
                ORDER BY r.capacity, r.room_id
                """,
                (min_capacity, booking_date, end_time, start_time),
            ).fetchall()
        return [
            dict(row)
            for row in rows
            if self._is_room_open(
                row["room_id"], booking_date, start_time, end_time
            )
        ]

    def create_booking(
        self,
        room_id: str,
        booking_date: str,
        start_time: str,
        end_time: str,
        purpose: str,
    ) -> dict[str, Any]:
        room_id = room_id.strip().upper()
        booking_date = self._validate_date(booking_date)
        start_time = self._validate_time(start_time)
        end_time = self._validate_time(end_time)
        purpose = purpose.strip()
        self._validate_slot_rules(room_id, booking_date, start_time, end_time)
        if not purpose:
            raise BookingError("用途不可空白。")

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            room = connection.execute(
                "SELECT room_id, name FROM rooms WHERE room_id = ?", (room_id,)
            ).fetchone()
            if room is None:
                raise BookingError("找不到這個空間編號。")
            conflict = connection.execute(
                """
                SELECT booking_id FROM bookings
                WHERE room_id = ? AND booking_date = ? AND status = 'confirmed'
                  AND start_time < ? AND end_time > ?
                """,
                (room_id, booking_date, end_time, start_time),
            ).fetchone()
            if conflict:
                raise BookingError("該空間在指定時段已被預約。")
            active_count = connection.execute(
                """
                SELECT COUNT(*) FROM bookings
                WHERE requester_id = 'DEMO-STUDENT'
                  AND booking_date = ? AND status = 'confirmed'
                """,
                (booking_date,),
            ).fetchone()[0]
            if active_count >= 2:
                raise BookingError("同一使用者同一天最多保留 2 筆有效預約。")
            next_number = connection.execute(
                "SELECT COALESCE(MAX(CAST(SUBSTR(booking_id, 3) AS INTEGER)), 0) + 1 FROM bookings"
            ).fetchone()[0]
            booking_id = f"BK{next_number:04d}"
            created_at = datetime.now().astimezone().isoformat(timespec="seconds")
            connection.execute(
                """
                INSERT INTO bookings(
                    booking_id, room_id, booking_date, start_time, end_time,
                    purpose, requester_id, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'DEMO-STUDENT', 'confirmed', ?)
                """,
                (booking_id, room_id, booking_date, start_time, end_time, purpose, created_at),
            )
            connection.commit()

        return {
            "booking_id": booking_id,
            "room_id": room_id,
            "room_name": room["name"],
            "booking_date": booking_date,
            "start_time": start_time,
            "end_time": end_time,
            "purpose": purpose,
            "status": "confirmed",
        }

    def get_booking(self, booking_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT b.booking_id, b.room_id, r.name AS room_name,
                       b.booking_date, b.start_time, b.end_time, b.purpose, b.status
                FROM bookings AS b
                JOIN rooms AS r ON r.room_id = b.room_id
                WHERE UPPER(b.booking_id) = UPPER(?)
                """,
                (booking_id.strip(),),
            ).fetchone()
        return dict(row) if row else None

    def cancel_booking(self, booking_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT booking_id, status FROM bookings WHERE UPPER(booking_id) = UPPER(?)",
                (booking_id.strip(),),
            ).fetchone()
            if row is None:
                return None
            if row["status"] != "cancelled":
                connection.execute(
                    "UPDATE bookings SET status = 'cancelled' WHERE booking_id = ?",
                    (row["booking_id"],),
                )
            connection.commit()
        return {"booking_id": row["booking_id"], "status": "cancelled"}
