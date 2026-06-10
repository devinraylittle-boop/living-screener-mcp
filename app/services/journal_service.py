from __future__ import annotations

from app.storage.repositories import EventRepository


class JournalService:
    def __init__(self, events: EventRepository):
        self.events = events

    def log_trade_decision(self, decision: dict) -> dict:
        return self.events.log("trade_decision", decision)

    def log_trade_result(self, result: dict) -> dict:
        return self.events.log("trade_result", result)
