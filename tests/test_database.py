from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from campus_assistant.db import BookingError, CampusDatabase


class CampusDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = CampusDatabase(Path(self.temp_dir.name) / "test.db")
        self.future_date = (date.today() + timedelta(days=7)).isoformat()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_get_cancel_and_reopen_slot(self) -> None:
        booking = self.db.create_booking(
            "LIB-201", self.future_date, "10:00", "11:00", "讀書會"
        )
        self.assertEqual("BK0001", booking["booking_id"])
        self.assertEqual("confirmed", self.db.get_booking("BK0001")["status"])

        rooms = self.db.list_available_rooms(self.future_date, "10:30", "11:30", 5)
        self.assertNotIn("LIB-201", {room["room_id"] for room in rooms})

        self.db.cancel_booking("BK0001")
        self.assertEqual("cancelled", self.db.get_booking("BK0001")["status"])
        rooms = self.db.list_available_rooms(self.future_date, "10:30", "11:30", 5)
        self.assertIn("LIB-201", {room["room_id"] for room in rooms})

    def test_rejects_overlapping_booking(self) -> None:
        self.db.create_booking(
            "LIB-201", self.future_date, "10:00", "11:00", "第一次會議"
        )
        with self.assertRaisesRegex(BookingError, "已被預約"):
            self.db.create_booking(
                "LIB-201", self.future_date, "10:30", "11:30", "衝突會議"
            )

    def test_enforces_duration_and_opening_hours(self) -> None:
        with self.assertRaisesRegex(BookingError, "最長 3 小時"):
            self.db.create_booking(
                "ACT-102", self.future_date, "10:00", "14:00", "過長活動"
            )
        with self.assertRaisesRegex(BookingError, "開放時間"):
            self.db.create_booking(
                "LIB-201", self.future_date, "06:00", "07:00", "過早活動"
            )


if __name__ == "__main__":
    unittest.main()
