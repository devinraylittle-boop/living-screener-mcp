from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from app.services.pending_order_service import PendingOrderService
from tests.helpers import TempContainer


class FakeScanner:
    def __init__(self, item: dict):
        self.item = item

    def run_market_scan(self, mode: str, tickers: list[str], max_candidates: int) -> dict:
        del mode, tickers, max_candidates
        if self.item["status"] == "CANDIDATE":
            return {"top_candidates": [self.item], "pass_list": []}
        return {"top_candidates": [], "pass_list": [self.item]}


class FakeOptions:
    def validate_chain(self, ticker: str, direction: str, max_contract_price: float | None) -> dict:
        del ticker, direction, max_contract_price
        return {"status": "OPTIONS_CHAIN_ACCEPTABLE"}


def ago(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()


class PendingOrderServiceTests(unittest.TestCase):
    def test_pending_buy_older_than_60_seconds_requires_reconsideration(self) -> None:
        with TempContainer() as container:
            service = PendingOrderService(
                container.settings,
                container.events,
                FakeScanner({"ticker": "PG", "status": "CANDIDATE", "quote_summary": {"price": 100.0}}),
                FakeOptions(),
            )
            result = service.review_pending_buy("PG", ago(90), 100.0)

        self.assertEqual(result["status"], "RECONSIDER_PENDING_BUY")
        self.assertIn("older than the configured recheck window", " ".join(result["reasons"]))
        self.assertFalse(result["can_cancel_order_from_this_mcp"])

    def test_pending_buy_inside_window_can_remain_valid_for_review(self) -> None:
        with TempContainer() as container:
            service = PendingOrderService(
                container.settings,
                container.events,
                FakeScanner({"ticker": "PG", "status": "CANDIDATE", "quote_summary": {"price": 100.0}}),
                FakeOptions(),
            )
            result = service.review_pending_buy("PG", ago(30), 100.0)

        self.assertEqual(result["status"], "STILL_VALID_FOR_REVIEW")
        self.assertEqual(result["reasons"], [])

    def test_pending_buy_reconsiders_when_stock_setup_fails(self) -> None:
        with TempContainer() as container:
            service = PendingOrderService(
                container.settings,
                container.events,
                FakeScanner({"ticker": "PG", "status": "PASS", "quote_summary": {"price": 100.0}}),
                FakeOptions(),
            )
            result = service.review_pending_buy("PG", ago(10), 100.0)

        self.assertEqual(result["status"], "RECONSIDER_PENDING_BUY")
        self.assertIn("stock setup", " ".join(result["reasons"]).lower())
