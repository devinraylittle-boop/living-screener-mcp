from __future__ import annotations

import json
from typing import Any

from app.storage.database import Database
from app.utils import utc_now


class EventRepository:
    def __init__(self, database: Database):
        self.database = database
        self.database.init()

    def log(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO events (timestamp, event_type, payload_json) VALUES (?, ?, ?)",
                (timestamp, event_type, json.dumps(payload, sort_keys=True, default=str)),
            )
        return {"logged": True, "timestamp": timestamp, "event_type": event_type, **payload}

    def count(self, event_type: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS count FROM events"
        params = ()
        if event_type:
            sql += " WHERE event_type = ?"
            params = (event_type,)
        with self.database.connect() as connection:
            return int(connection.execute(sql, params).fetchone()["count"])

    def recent(self, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT id, timestamp, event_type, payload_json FROM events"
        params: tuple[Any, ...]
        if event_type:
            sql += " WHERE event_type = ?"
            params = (event_type, max(1, min(int(limit), 500)))
        else:
            params = (max(1, min(int(limit), 500)),)
        sql += " ORDER BY id DESC LIMIT ?"
        rows = []
        with self.database.connect() as connection:
            for row in connection.execute(sql, params).fetchall():
                try:
                    payload = json.loads(row["payload_json"])
                except json.JSONDecodeError:
                    payload = {"raw_payload": row["payload_json"]}
                rows.append(
                    {
                        "id": row["id"],
                        "timestamp": row["timestamp"],
                        "event_type": row["event_type"],
                        "payload": payload,
                    }
                )
        return rows


class RecommendationRepository:
    def __init__(self, database: Database):
        self.database = database
        self.database.init()

    def log(self, ticker: str, status: str, score: float, payload: dict[str, Any]) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO recommendations (timestamp, ticker, status, score, payload_json) VALUES (?, ?, ?, ?, ?)",
                (utc_now(), ticker.upper(), status, score, json.dumps(payload, sort_keys=True, default=str)),
            )
