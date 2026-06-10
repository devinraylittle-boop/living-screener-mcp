from __future__ import annotations

from app.storage.repositories import EventRepository


class PostmortemService:
    def __init__(self, events: EventRepository):
        self.events = events

    def run_postmortem(self, date: str | None = None) -> dict:
        return self.events.log("postmortem", {"date": date, "protocol": "30_day_review"})
