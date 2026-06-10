from __future__ import annotations

class OptionsDataStub:
    def get_chain(self, ticker: str) -> dict:
        return {"ticker": ticker.upper(), "contracts": [], "notes": "Options data not wired yet."}
