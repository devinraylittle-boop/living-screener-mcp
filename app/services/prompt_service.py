from __future__ import annotations

from app.storage.repositories import EventRepository


class PromptService:
    def __init__(self, events: EventRepository):
        self.events = events

    def generate_updated_prompt(self) -> dict:
        prompt = "Use Living Screener first. Use Robinhood MCP separately. If no clean edge exists, say PASS. Never place orders from Living Screener MCP."
        return self.events.log("prompt_generation", {"prompt": prompt})
