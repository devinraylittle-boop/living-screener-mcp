from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.paper_lifecycle_ledger import record_entry, record_exit, summarize


class PaperLifecycleLedgerTests(unittest.TestCase):
    def test_entry_and_exit_records_are_promotion_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper_lifecycle_ledger.jsonl"
            gates = Path(tmp) / "gates.json"
            gates.write_text(
                json.dumps(
                    {
                        "required_before_limited_autonomous_live": {
                            "min_closed_paper_trades": 1,
                            "min_distinct_market_days": 1,
                            "min_profit_factor_after_costs": 1.2,
                            "max_paper_drawdown_pct": 8.0,
                        }
                    }
                ),
                encoding="utf-8",
            )

            entry = record_entry(
                broker="alpaca",
                scope="scope-hash",
                symbol="CELH",
                order_id="entry-1",
                order_status="accepted",
                notional=250.0,
                quantity=5.0,
                reference_price=50.0,
                setup={"stock_score": 82, "bridge_evidence_profile": {"data_confidence_status": "HIGH"}},
                risk={"stop_loss_pct": 0.01, "take_profit_pct": 0.015},
                path=path,
            )
            exit_record = record_exit(
                broker="alpaca",
                scope="scope-hash",
                symbol="CELH",
                order_id="exit-1",
                order_status="accepted",
                quantity=5.0,
                entry_reference_price=50.0,
                exit_reference_price=52.0,
                exit_reason="take_profit",
                path=path,
            )
            report = summarize(path, gates)

            self.assertEqual(entry["event"], "paper_entry")
            self.assertFalse(entry["real_cash"])
            self.assertEqual(exit_record["pnl_dollars"], 10.0)
            self.assertEqual(report["status"], "PAPER_PROMOTION_READY")
            self.assertEqual(report["closed_trade_count"], 1)
            self.assertEqual(report["win_rate"], 1.0)

    def test_report_blocks_when_sample_size_is_too_small(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper_lifecycle_ledger.jsonl"
            gates = Path(tmp) / "gates.json"
            gates.write_text(
                json.dumps(
                    {
                        "required_before_limited_autonomous_live": {
                            "min_closed_paper_trades": 100,
                            "min_distinct_market_days": 20,
                            "min_profit_factor_after_costs": 1.2,
                            "max_paper_drawdown_pct": 8.0,
                        }
                    }
                ),
                encoding="utf-8",
            )

            record_entry(
                broker="alpaca",
                scope="scope-hash",
                symbol="MU",
                order_id="entry-1",
                order_status="accepted",
                notional=250.0,
                quantity=10.0,
                reference_price=25.0,
                setup={},
                risk={},
                path=path,
            )
            record_exit(
                broker="alpaca",
                scope="scope-hash",
                symbol="MU",
                order_id="exit-1",
                order_status="accepted",
                quantity=10.0,
                entry_reference_price=25.0,
                exit_reference_price=24.5,
                exit_reason="stop_loss",
                path=path,
            )
            report = summarize(path, gates)

            self.assertEqual(report["status"], "PAPER_PROMOTION_BLOCKED")
            self.assertIn("min_closed_paper_trades", report["blockers"])
            self.assertIn("min_distinct_market_days", report["blockers"])


if __name__ == "__main__":
    unittest.main()

