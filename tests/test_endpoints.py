from __future__ import annotations

import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from app.main import create_app


class EndpointTests(unittest.TestCase):
    def test_health_config_and_version_are_safe(self) -> None:
        client = TestClient(create_app())
        health = client.get("/health")
        config = client.get("/config")
        version = client.get("/version")
        tools = client.get("/tools")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(config.status_code, 200)
        self.assertEqual(version.status_code, 200)
        self.assertEqual(tools.status_code, 200)
        self.assertIn("build_version", version.json())
        self.assertIn("has_finnhub_api_key", config.json())
        self.assertNotIn("finnhub_api_key", config.json())
        self.assertFalse(version.json()["can_place_order_from_this_mcp"])
        self.assertIn("get_version", tools.json()["tools"])
        self.assertIn("version", tools.json()["tools"])
        self.assertIn("get_build_version", tools.json()["tools"])
        self.assertIn("run_scalp_scan", tools.json()["tools"])
        self.assertIn("market_readiness_check", tools.json()["tools"])
        self.assertIn("run_review_harvest", tools.json()["tools"])
        self.assertIn("get_market_session_playbook", tools.json()["tools"])
        self.assertIn("run_latest_harvest_followup", tools.json()["tools"])
        self.assertIn("get_ops_command_center", tools.json()["tools"])
        self.assertIn("run_morning_readiness_autopilot", tools.json()["tools"])
        self.assertIn("run_live_review_cycle", tools.json()["tools"])
        self.assertIn("review_candidate_for_options", tools.json()["tools"])
        self.assertIn("validate_broker_option_snapshot", tools.json()["tools"])
        self.assertIn("build_manual_trade_preflight_ticket", tools.json()["tools"])
        self.assertIn("log_manual_option_paper_entry", tools.json()["tools"])
        self.assertIn("close_manual_option_paper_trade", tools.json()["tools"])
        self.assertIn("summarize_manual_option_paper_trades", tools.json()["tools"])
        self.assertIn("export_journal_checkpoint", tools.json()["tools"])
        self.assertIn("log_review_decision", tools.json()["tools"])
        self.assertIn("check_review_outcome", tools.json()["tools"])
        self.assertIn("summarize_review_outcomes", tools.json()["tools"])
        self.assertIn("log_research_snapshot", tools.json()["tools"])
        self.assertIn("classify_review_outcome", tools.json()["tools"])
        self.assertIn("summarize_learning", tools.json()["tools"])
        self.assertIn("generate_learning_rule_proposals", tools.json()["tools"])
        self.assertIn("review_pending_buy_order", tools.json()["tools"])
        self.assertIn("get_crypto_paper_rules", tools.json()["tools"])
        self.assertIn("start_crypto_paper_session", tools.json()["tools"])
        self.assertIn("run_crypto_paper_backtest", tools.json()["tools"])
        self.assertIn("get_offhours_research_plan", tools.json()["tools"])
        self.assertIn("run_global_research_scan", tools.json()["tools"])
        self.assertIn("get_trading_monster_blueprint", tools.json()["tools"])
        self.assertIn("get_feature_registry", tools.json()["tools"])
        self.assertIn("get_scoring_model", tools.json()["tools"])
        self.assertIn("explain_premove_score", tools.json()["tools"])
        self.assertIn("build_evidence_packet", tools.json()["tools"])
        self.assertIn("build_evidence_packets_from_scan", tools.json()["tools"])
        self.assertIn("summarize_evidence_packets", tools.json()["tools"])
        self.assertIn("build_setup_fingerprint", tools.json()["tools"])
        self.assertIn("compare_setup_memory", tools.json()["tools"])

    def test_browser_fallback_endpoints_are_review_only(self) -> None:
        client = TestClient(create_app())

        safety = client.get("/safety")
        missing_ticker = client.get("/review/options")
        missing_outcome = client.get("/review/outcome")

        self.assertEqual(safety.status_code, 200)
        self.assertFalse(safety.json()["can_place_order_from_this_mcp"])
        self.assertFalse(safety.json()["can_cancel_order_from_this_mcp"])
        self.assertEqual(missing_ticker.status_code, 400)
        self.assertFalse(missing_ticker.json()["can_place_order_from_this_mcp"])
        self.assertEqual(missing_outcome.status_code, 200)
        self.assertEqual(missing_outcome.json()["result"]["status"], "OUTCOME_UNAVAILABLE")

    def test_options_review_can_render_human_readable_html(self) -> None:
        fake_review = {
            "ticker": "SMCI",
            "status": "REVIEW_ONLY_OPTIONS_READY",
            "reason": "Stock setup and options-chain quality both passed review gates.",
            "stock_setup": {
                "ticker": "SMCI",
                "status": "CANDIDATE",
                "score": 76,
                "direction": "short",
                "key_signals": {
                    "relative_volume": 0.27,
                    "relative_volume_status": "same_time_of_day",
                    "above_vwap": False,
                    "below_vwap": True,
                    "vwap": 44.13,
                },
            },
            "options_chain_validation": {
                "status": "OPTIONS_CHAIN_ACCEPTABLE",
                "best_rejected_contracts": [
                    {
                        "contract_symbol": "SMCI_TEST",
                        "expiration": "2026-06-12",
                        "strike": 35,
                        "days_to_expiration": 3,
                        "bid": 0.19,
                        "ask": 0.21,
                        "spread_pct": 0.1,
                        "volume": 100,
                        "open_interest": 500,
                        "reasons": ["Bid/ask spread too wide."],
                        "closest_to_pass_reason": "Would pass spread gate if spread improved.",
                    }
                ],
            },
            "small_account_review": {
                "status": "SMALL_ACCOUNT_SCALP_ACCEPTABLE",
                "priority_score": 69,
                "friction_adjusted_score": 82,
                "friction_band": "MANAGEABLE_FRICTION",
                "friction_adjusted_review": {
                    "score": 82,
                    "band": "MANAGEABLE_FRICTION",
                    "penalties": [{"name": "spread_wide", "penalty": 10, "reason": "Spread is wider than preferred."}],
                    "components": {
                        "absolute_spread": 0.02,
                        "estimated_round_trip_slippage_dollars": 2,
                        "slippage_pct_of_max_loss": 0.0952,
                        "volume": 1358,
                        "open_interest": 1007,
                    },
                },
                "selected_contract": {
                    "contract_symbol": "SMCI260612P00035000",
                    "expiration": "2026-06-12",
                    "strike": 35,
                    "days_to_expiration": 3,
                    "bid": 0.19,
                    "ask": 0.21,
                    "spread_pct": 0.1,
                    "volume": 1358,
                    "open_interest": 1007,
                    "max_loss_dollars": 21,
                },
                "warnings": ["Selected contract spread is wider than preferred."],
            },
            "warnings": ["Selected contract spread is wider than preferred."],
            "setup_memory": {
                "memory_signal": "NO_MEMORY_YET",
                "fingerprint": {"setup_key": "demo-key", "tags": ["wide_spread"]},
                "similar_review_summary": {"sample_size": 0},
                "similar_lesson_summary": {"sample_size": 0, "average_directional_return": None},
            },
        }
        client = TestClient(create_app())
        with patch("app.fallback_endpoints._review_candidate_for_options", return_value=fake_review):
            html = client.get("/review/options?ticker=SMCI&direction=put&mode=scalp_review", headers={"accept": "text/html"})
            json_response = client.get("/review/options?ticker=SMCI&direction=put&mode=scalp_review&format=json", headers={"accept": "text/html"})

        self.assertEqual(html.status_code, 200)
        self.assertIn("text/html", html.headers["content-type"])
        self.assertIn("SMCI Options Review", html.text)
        self.assertIn("SMALL_ACCOUNT_SCALP_ACCEPTABLE", html.text)
        self.assertIn("Friction Review", html.text)
        self.assertIn("MANAGEABLE_FRICTION", html.text)
        self.assertIn("Setup Memory", html.text)
        self.assertIn("NO_MEMORY_YET", html.text)
        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(json_response.json()["result"]["ticker"], "SMCI")

    def test_learning_endpoints_are_review_only(self) -> None:
        client = TestClient(create_app())
        payload = {
            "snapshot": {
                "ticker": "SOFI",
                "status": "REVIEW_ONLY_OPTIONS_READY",
                "stock_setup": {
                    "ticker": "SOFI",
                    "status": "CANDIDATE",
                    "score": 94,
                    "direction": "short",
                    "key_signals": {"relative_volume": 0.7},
                },
                "small_account_review": {"status": "SMALL_ACCOUNT_SCALP_ACCEPTABLE", "warnings": ["Selected contract spread is wider than preferred."]},
            },
            "outcome": {"current_return_pct": -0.006, "max_favorable_excursion": 0.001, "max_adverse_excursion": -0.01},
        }

        classified = client.post("/learning/classify", json=payload)
        proposals = client.post(
            "/learning/proposals",
            json={
                "classifications": [
                    {"classification": "FALSE_POSITIVE", "lesson_tags": ["wide_spread"], "outcome_summary": {"directional_return": -0.004}},
                    {"classification": "FALSE_POSITIVE", "lesson_tags": ["wide_spread"], "outcome_summary": {"directional_return": -0.005}},
                    {"classification": "GOOD_SIGNAL", "lesson_tags": ["wide_spread"], "outcome_summary": {"directional_return": 0.002}},
                ]
            },
        )
        setup_memory = client.post("/learning/setup-memory", json={"snapshot": payload["snapshot"]})
        dashboard = client.get("/learning/dashboard", headers={"accept": "text/html"})

        self.assertEqual(classified.status_code, 200)
        self.assertEqual(classified.json()["result"]["classification"], "FALSE_POSITIVE")
        self.assertFalse(classified.json()["can_place_order_from_this_mcp"])
        self.assertEqual(proposals.status_code, 200)
        self.assertTrue(proposals.json()["result"]["do_not_auto_apply"])
        self.assertEqual(setup_memory.status_code, 200)
        self.assertEqual(setup_memory.json()["result"]["status"], "SETUP_MEMORY_READY")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Learning Dashboard", dashboard.text)

    def test_market_ops_endpoints_are_review_only(self) -> None:
        fake_readiness = {
            "status": "MARKET_REVIEW_READY",
            "candidate_count": 2,
            "valid_row_count": 5,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        fake_harvest = {
            "status": "REVIEW_HARVEST_READY",
            "mode": "scalp_review",
            "reviewed_count": 2,
            "eligible_count": 1,
            "watch_only_count": 1,
            "ranked_candidates": [
                {
                    "ticker": "SOFI",
                    "status": "REVIEW_ONLY_OPTIONS_READY",
                    "direction": "short",
                    "score": 86,
                    "priority_score": 82,
                    "friction_adjusted_score": 88,
                    "contract": "SOFI260612P00015000",
                    "ask": 0.08,
                    "max_loss_dollars": 8,
                    "memory_signal": "NO_MEMORY_YET",
                }
            ],
            "watch_only": [],
            "followup_checks": [{"ticker": "SOFI", "check_after_minutes": [15, 30, 60]}],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        fake_playbook = {
            "status": "SESSION_PLAYBOOK_READY",
            "generated_at": "2026-06-09T20:00:00+00:00",
            "universe": ["SOFI", "SMCI"],
            "account_value_reference": 50,
            "small_account_contract_cap": 1.0,
            "session_blocks": [
                {
                    "central_time": "08:50-10:15",
                    "label": "First review harvest",
                    "intent": "Run harvest loops.",
                    "actions": ["/ops/review-harvest"],
                    "pass_condition": "Clean candidate.",
                    "fail_condition": "No clean candidate.",
                }
            ],
            "manual_trade_gate": ["Build and safety confirmed."],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        fake_followup = {
            "status": "HARVEST_FOLLOWUP_COMPLETE",
            "harvest_event_id": 1,
            "checks_requested": 1,
            "checks_completed": 1,
            "classify": True,
            "outcomes": [{"ticker": "SOFI", "verdict": "HELPED", "current_return_pct": 0.004}],
            "classifications": [{"ticker": "SOFI", "classification": "GOOD_SIGNAL", "reason": "Worked.", "lesson_tags": ["wide_spread"]}],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        fake_command_center = {
            "status": "READY_FOR_HARVEST",
            "universe": ["SOFI", "SMCI"],
            "next_action": {"label": "Run review harvest.", "reason": "Ready.", "endpoint": "/ops/review-harvest"},
            "latest": {"market_readiness": {"status": "MARKET_REVIEW_READY"}},
            "action_links": {"review_harvest": "/ops/review-harvest", "learning_dashboard": "/learning/dashboard"},
            "latest_learning_labels": [],
            "manual_trade_gate": ["Command center build and safety are confirmed."],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        fake_autopilot = {
            "status": "AUTOPILOT_READY_FOR_HARVEST",
            "next_action": "Run review harvest, then options-review only valid directional stock candidates.",
            "readiness": {"status": "MARKET_REVIEW_READY", "candidate_count": 1, "valid_row_count": 2, "quote_problem_count": 0},
            "paper_ledger": {"status": "PAPER_LEDGER_READY", "entry_count": 0, "open_count": 0, "closed_count": 0, "total_pnl_dollars": 0},
            "session_blocks": [{"central_time": "08:50-10:15", "label": "First review harvest", "intent": "Review valid candidates."}],
            "manual_trade_gate": ["Use limit-only review."],
            "action_links": {"review_harvest": "/ops/review-harvest", "paper_ledger": "/paper/options/summary"},
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        fake_live_cycle = {
            "status": "LIVE_CYCLE_CANDIDATES_READY",
            "next_action": "Manually inspect the top candidate in broker, then run manual preflight with broker-visible bid/ask/volume/OI.",
            "manual_preflight_required": True,
            "readiness": {"status": "MARKET_REVIEW_READY", "data_status": "available", "valid_row_count": 2, "quote_problem_count": 0},
            "harvest": {"status": "REVIEW_HARVEST_READY", "reviewed_count": 1, "eligible_count": 1, "watch_only_count": 0},
            "ranked_candidates": [
                {
                    "ticker": "SOFI",
                    "status": "REVIEW_ONLY_OPTIONS_READY",
                    "direction": "put",
                    "stock_setup": {"ticker": "SOFI", "score": 82, "direction": "short"},
                    "small_account_review": {"status": "SMALL_ACCOUNT_SCALP_ACCEPTABLE", "priority_score": 90},
                    "selected_contract": {"contract_symbol": "SOFI260612P00015000", "ask": 0.05, "max_loss_dollars": 5.0},
                }
            ],
            "watch_only_reviews": [],
            "paper_ledger": {"status": "PAPER_LEDGER_READY", "entry_count": 0, "open_count": 0, "closed_count": 0, "total_pnl_dollars": 0},
            "manual_trade_gate": ["Manual preflight returns MANUAL_PREFLIGHT_READY."],
            "action_links": {"manual_preflight": "/review/manual-preflight", "paper_ledger": "/paper/options/summary"},
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        fake_preflight = {
            "status": "MANUAL_PREFLIGHT_READY",
            "ticker": "SOFI",
            "direction": "put",
            "account_value_reference": 50,
            "option_validation": {"status": "OPTIONS_CHAIN_ACCEPTABLE"},
            "risk_check": {"status": "APPROVE_FOR_REVIEW"},
            "selected_contract": {
                "contract_symbol": "SOFI260612P00015000",
                "bid": 0.04,
                "ask": 0.045,
                "spread_pct": 0.1176,
                "volume": 500,
                "open_interest": 2000,
                "days_to_expiration": 3,
                "strike": 15,
            },
            "manual_ticket": {
                "contract_symbol": "SOFI260612P00015000",
                "order_type": "limit_only",
                "max_review_ask": 0.045,
                "max_loss_dollars": 4.5,
                "quantity": 1,
                "broker_action_required": True,
                "mcp_can_execute": False,
            },
            "blocking_reasons": [],
            "warnings": [],
            "checklist": ["Use limit-only review."],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        client = TestClient(create_app())
        with patch("app.fallback_endpoints._market_readiness_check", return_value=fake_readiness), patch(
            "app.fallback_endpoints._run_review_harvest", return_value=fake_harvest
        ), patch("app.fallback_endpoints._get_market_session_playbook", return_value=fake_playbook), patch(
            "app.fallback_endpoints._run_latest_harvest_followup", return_value=fake_followup
        ), patch(
            "app.fallback_endpoints._get_ops_command_center", return_value=fake_command_center
        ), patch(
            "app.fallback_endpoints._run_morning_readiness_autopilot", return_value=fake_autopilot
        ), patch(
            "app.fallback_endpoints._run_live_review_cycle", return_value=fake_live_cycle
        ), patch(
            "app.fallback_endpoints._build_manual_trade_preflight_ticket", return_value=fake_preflight
        ):
            readiness = client.get("/ops/market-readiness?tickers=SOFI,SMCI")
            harvest_json = client.get("/ops/review-harvest?tickers=SOFI,SMCI")
            harvest_html = client.get("/ops/review-harvest?tickers=SOFI,SMCI", headers={"accept": "text/html"})
            playbook_html = client.get("/ops/session-playbook?tickers=SOFI,SMCI", headers={"accept": "text/html"})
            followup_html = client.get("/ops/harvest-followup?limit=5&classify=true", headers={"accept": "text/html"})
            command_center_html = client.get("/ops/command-center?tickers=SOFI,SMCI", headers={"accept": "text/html"})
            autopilot_html = client.get("/ops/morning-autopilot?tickers=SOFI,SMCI", headers={"accept": "text/html"})
            live_cycle_html = client.get("/ops/live-review-cycle?tickers=SOFI,SMCI", headers={"accept": "text/html"})
            preflight_html = client.get(
                "/review/manual-preflight?ticker=SOFI&contract_symbol=SOFI260612P00015000&direction=put&bid=0.04&ask=0.045&volume=500&open_interest=2000&dte=3&strike=15",
                headers={"accept": "text/html"},
            )

        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(readiness.json()["result"]["status"], "MARKET_REVIEW_READY")
        self.assertFalse(readiness.json()["can_place_order_from_this_mcp"])
        self.assertEqual(harvest_json.status_code, 200)
        self.assertEqual(harvest_json.json()["result"]["status"], "REVIEW_HARVEST_READY")
        self.assertEqual(harvest_json.json()["result"]["eligible_count"], 1)
        self.assertFalse(harvest_json.json()["can_cancel_order_from_this_mcp"])
        self.assertEqual(harvest_html.status_code, 200)
        self.assertIn("Review Harvest", harvest_html.text)
        self.assertIn("SOFI260612P00015000", harvest_html.text)
        self.assertEqual(playbook_html.status_code, 200)
        self.assertIn("Market Session Playbook", playbook_html.text)
        self.assertIn("First review harvest", playbook_html.text)
        self.assertEqual(followup_html.status_code, 200)
        self.assertIn("Harvest Follow-Up", followup_html.text)
        self.assertIn("GOOD_SIGNAL", followup_html.text)
        self.assertEqual(command_center_html.status_code, 200)
        self.assertIn("Ops Command Center", command_center_html.text)
        self.assertIn("Run review harvest.", command_center_html.text)
        self.assertEqual(autopilot_html.status_code, 200)
        self.assertIn("Morning Readiness Autopilot", autopilot_html.text)
        self.assertIn("Run review harvest", autopilot_html.text)
        self.assertEqual(live_cycle_html.status_code, 200)
        self.assertIn("Live Review Cycle", live_cycle_html.text)
        self.assertIn("SOFI260612P00015000", live_cycle_html.text)
        self.assertEqual(preflight_html.status_code, 200)
        self.assertIn("Manual Trade Preflight", preflight_html.text)
        self.assertIn("SOFI260612P00015000", preflight_html.text)

    def test_offhours_and_crypto_fallbacks_are_review_only(self) -> None:
        fake_global_scan = {
            "status": "GLOBAL_RESEARCH_SCAN_COMPLETE",
            "market": "crypto",
            "period": "5d",
            "interval": "5m",
            "top_candidates": [
                {
                    "symbol": "ETH-USD",
                    "status": "STUDY_CANDIDATE",
                    "score": 72,
                    "direction": "long",
                    "feature_summary": {"relative_volume": 1.8, "range_expansion": 1.5, "compression_break": True},
                    "lesson_tags": ["rvol_expansion", "compression_break"],
                }
            ],
            "watch_list": [],
            "pass_list": [],
        }
        fake_crypto = {
            "result": "PASS",
            "period": "5d",
            "interval": "5m",
            "best_symbol": "ETH-USD",
            "aggregate": {"aggregate_return_pct": 0.01, "total_trade_count": 2, "win_rate": 0.5},
            "results": [{"symbol": "ETH-USD", "symbol_recommendation": "PAPER_ELIGIBLE", "trade_count": 2, "win_rate": 0.5, "return_pct": 0.01, "max_drawdown_pct": 0}],
        }
        client = TestClient(create_app())
        with patch("app.fallback_endpoints.container.global_research.run_global_research_scan", return_value=fake_global_scan), patch(
            "app.fallback_endpoints.container.crypto_paper.run_backtest", return_value=fake_crypto
        ):
            plan = client.get("/research/offhours")
            scan = client.get("/research/global-scan?market=crypto", headers={"accept": "text/html"})
            rules = client.get("/crypto/rules")
            backtest = client.get("/crypto/backtest?symbols=ETH-USD,SOL-USD", headers={"accept": "text/html"})

        self.assertEqual(plan.status_code, 200)
        self.assertFalse(plan.json()["can_place_order_from_this_mcp"])
        self.assertEqual(scan.status_code, 200)
        self.assertIn("Off-Hours Research Scan", scan.text)
        self.assertEqual(rules.status_code, 200)
        self.assertFalse(rules.json()["can_place_order_from_this_mcp"])
        self.assertEqual(backtest.status_code, 200)
        self.assertIn("Crypto Paper Backtest", backtest.text)

    def test_premove_research_endpoints_are_review_only(self) -> None:
        client = TestClient(create_app())

        blueprint = client.get("/research/blueprint", headers={"accept": "text/html"})
        features = client.get("/research/features")
        scoring = client.get("/research/scoring-model", headers={"accept": "text/html"})
        explanation = client.post(
            "/research/explain-score",
            json={
                "ticker": "SMCI",
                "score": 76,
                "direction": "short",
                "key_signals": {
                    "relative_volume": 0.8,
                    "above_vwap": False,
                    "below_vwap": True,
                    "pct_change_vs_previous_close": -0.012,
                    "trend_pct": -0.01,
                    "recent_trend_pct": -0.003,
                },
            },
        )

        self.assertEqual(blueprint.status_code, 200)
        self.assertIn("Trading Monster Blueprint", blueprint.text)
        self.assertEqual(features.status_code, 200)
        self.assertFalse(features.json()["can_place_order_from_this_mcp"])
        self.assertEqual(scoring.status_code, 200)
        self.assertIn("Scoring Model", scoring.text)
        self.assertEqual(explanation.status_code, 200)
        self.assertEqual(explanation.json()["result"]["status"], "SCORE_EXPLANATION_READY")
        self.assertFalse(explanation.json()["can_place_order_from_this_mcp"])

    def test_evidence_packet_endpoints_are_review_only(self) -> None:
        client = TestClient(create_app())
        item = {
            "ticker": "SMCI",
            "status": "CANDIDATE",
            "score": 76,
            "confidence": "low-medium",
            "direction": "short",
            "setup_type": "scalp_review",
            "quote_summary": {"provider": "finnhub", "timestamp": "2026-06-09T20:00:00Z", "freshness_status": "LAST_REGULAR_SESSION_ACCEPTED", "derived_from_candles": False},
            "candle_summary": {"provider": "yfinance", "last_timestamp": "2026-06-09T19:55:00Z", "freshness_status": "LAST_REGULAR_SESSION_ACCEPTED", "count": 390},
            "quality_gates": {"stock_setup_quality": "VALID_CANDIDATE", "options_chain_quality": "NOT_VALIDATED"},
            "key_signals": {
                "relative_volume": 0.77,
                "relative_volume_status": "same_time_of_day",
                "above_vwap": False,
                "below_vwap": True,
                "evidence_scorecard": {
                    "missing_or_planned_modules": ["catalyst_context", "relative_strength_vs_spy_and_sector", "full_l2_order_flow"]
                },
            },
        }

        packet = client.post("/research/evidence-packet", json={"item": item})
        batch = client.post("/research/evidence-packets-from-scan", json={"scan_result": {"top_candidates": [item], "pass_list": []}})
        summary = client.post("/research/evidence-summary", json={"packets": [packet.json()["result"]]})

        self.assertEqual(packet.status_code, 200)
        self.assertEqual(packet.json()["result"]["packet_type"], "point_in_time_scan_evidence")
        self.assertFalse(packet.json()["can_place_order_from_this_mcp"])
        self.assertEqual(batch.status_code, 200)
        self.assertEqual(batch.json()["result"]["packet_count"], 1)
        self.assertEqual(summary.status_code, 200)
        self.assertIn("relative_strength_missing", summary.json()["result"]["summary"]["top_data_flags"])

    def test_debug_validation_endpoints_are_static_and_safe(self) -> None:
        client = TestClient(create_app())

        full = client.get("/health/full?expected_build_version=2026.06.10-journal-checkpoint")
        mismatch = client.get("/health/full?expected_build_version=wrong-build")
        manifest = client.get("/debug/tool-manifest")
        schema = client.get("/debug/scan-schema?expected_build_version=2026.06.10-journal-checkpoint")

        self.assertEqual(full.status_code, 200)
        self.assertEqual(full.json()["result"]["status"], "OK")
        self.assertTrue(full.json()["result"]["build_matches_expected"])
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(mismatch.json()["result"]["status"], "BUILD_MISMATCH")
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.json()["result"]["status"], "TOOL_MANIFEST_READY")
        self.assertTrue(manifest.json()["result"]["required_tools"]["market_readiness_check"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["run_review_harvest"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["get_market_session_playbook"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["run_latest_harvest_followup"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["get_ops_command_center"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["run_morning_readiness_autopilot"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["run_live_review_cycle"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["build_manual_trade_preflight_ticket"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["log_manual_option_paper_entry"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["close_manual_option_paper_trade"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["summarize_manual_option_paper_trades"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["export_journal_checkpoint"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["summarize_evidence_packets"])
        self.assertTrue(manifest.json()["result"]["required_tools"]["compare_setup_memory"])
        self.assertEqual(schema.status_code, 200)
        self.assertEqual(schema.json()["result"]["status"], "SCAN_SCHEMA_READY")
        example = schema.json()["result"]["example_candidate"]
        self.assertIn("evidence_scorecard", example["key_signals"])
        self.assertIn("relative_strength", example["key_signals"])
        self.assertIn("evidence_packet", example)
        options_preview = schema.json()["result"]["options_review_schema_preview"]
        self.assertEqual(options_preview["small_account_review"]["friction_band"], "LOW_FRICTION")
        setup_preview = schema.json()["result"]["setup_memory_schema_preview"]
        self.assertEqual(setup_preview["status"], "SETUP_MEMORY_READY")
        harvest_preview = schema.json()["result"]["review_harvest_schema_preview"]
        self.assertEqual(harvest_preview["status"], "REVIEW_HARVEST_READY")
        playbook_preview = schema.json()["result"]["session_playbook_schema_preview"]
        self.assertEqual(playbook_preview["status"], "SESSION_PLAYBOOK_READY")
        followup_preview = schema.json()["result"]["harvest_followup_schema_preview"]
        self.assertEqual(followup_preview["status"], "HARVEST_FOLLOWUP_COMPLETE")
        command_center_preview = schema.json()["result"]["ops_command_center_schema_preview"]
        self.assertEqual(command_center_preview["status"], "READY_FOR_HARVEST")
        autopilot_preview = schema.json()["result"]["morning_autopilot_schema_preview"]
        self.assertEqual(autopilot_preview["status"], "AUTOPILOT_READY_FOR_HARVEST")
        live_cycle_preview = schema.json()["result"]["live_review_cycle_schema_preview"]
        self.assertEqual(live_cycle_preview["status"], "LIVE_CYCLE_CANDIDATES_READY")
        preflight_preview = schema.json()["result"]["manual_preflight_schema_preview"]
        self.assertEqual(preflight_preview["status"], "MANUAL_PREFLIGHT_READY")
        ledger_preview = schema.json()["result"]["paper_option_ledger_schema_preview"]
        self.assertEqual(ledger_preview["status"], "PAPER_LEDGER_READY")
        checkpoint_preview = schema.json()["result"]["journal_checkpoint_schema_preview"]
        self.assertEqual(checkpoint_preview["status"], "JOURNAL_CHECKPOINT_READY")
        self.assertFalse(schema.json()["can_place_order_from_this_mcp"])

    def test_paper_option_ledger_endpoints_are_review_only(self) -> None:
        fake_entry = {
            "status": "PAPER_OPTION_ENTRY_OPEN",
            "id": 101,
            "ticker": "SOFI",
            "contract_symbol": "SOFI260612P00015000",
            "entry_price": 0.05,
            "quantity": 1,
            "paper_only": True,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "broker_action": False,
        }
        fake_close = {
            "status": "PAPER_OPTION_CLOSED",
            "entry_event_id": 101,
            "ticker": "SOFI",
            "contract_symbol": "SOFI260612P00015000",
            "pnl_dollars": 3.0,
            "return_pct": 0.6,
            "learning_classification": {"classification": "GOOD_SIGNAL"},
            "paper_only": True,
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        fake_summary = {
            "status": "PAPER_LEDGER_READY",
            "entry_count": 1,
            "closed_count": 1,
            "open_count": 0,
            "win_rate": 1.0,
            "total_pnl_dollars": 3.0,
            "average_pnl_dollars": 3.0,
            "open_entries": [],
            "recent_closes": [
                {
                    "entry_event_id": 101,
                    "ticker": "SOFI",
                    "contract_symbol": "SOFI260612P00015000",
                    "pnl_dollars": 3.0,
                    "return_pct": 0.6,
                    "classification": "GOOD_SIGNAL",
                }
            ],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        client = TestClient(create_app())
        with patch("app.fallback_endpoints._log_manual_option_paper_entry", return_value=fake_entry), patch(
            "app.fallback_endpoints._close_manual_option_paper_trade", return_value=fake_close
        ), patch("app.fallback_endpoints._summarize_manual_option_paper_trades", return_value=fake_summary):
            entry = client.post("/paper/options/entry", json={"ticket": {"status": "MANUAL_PREFLIGHT_READY"}, "fill_price": 0.05})
            close = client.post("/paper/options/close", json={"entry_id": 101, "exit_price": 0.08})
            summary = client.get("/paper/options/summary", headers={"accept": "text/html"})

        self.assertEqual(entry.status_code, 200)
        self.assertEqual(entry.json()["result"]["status"], "PAPER_OPTION_ENTRY_OPEN")
        self.assertFalse(entry.json()["can_place_order_from_this_mcp"])
        self.assertEqual(close.status_code, 200)
        self.assertEqual(close.json()["result"]["status"], "PAPER_OPTION_CLOSED")
        self.assertFalse(close.json()["can_cancel_order_from_this_mcp"])
        self.assertEqual(summary.status_code, 200)
        self.assertIn("Paper Option Ledger", summary.text)
        self.assertIn("SOFI260612P00015000", summary.text)

    def test_journal_checkpoint_endpoint_is_review_only(self) -> None:
        fake_checkpoint = {
            "status": "JOURNAL_CHECKPOINT_READY",
            "event_count": 2,
            "latest_event_id": 44,
            "checkpoint_event_id": 45,
            "event_type_counts": {"live_review_cycle": 1, "manual_option_paper_close": 1},
            "events": [
                {"id": 44, "timestamp": "2026-06-10T13:30:00Z", "event_type": "live_review_cycle", "payload": {"status": "NO_TRADE_PLAN"}}
            ],
            "restore_guidance": ["Save this JSON."],
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
        }
        client = TestClient(create_app())
        with patch("app.fallback_endpoints._export_journal_checkpoint", return_value=fake_checkpoint):
            checkpoint_json = client.get("/journal/checkpoint?limit=100")
            checkpoint_html = client.get("/journal/checkpoint?limit=100", headers={"accept": "text/html"})

        self.assertEqual(checkpoint_json.status_code, 200)
        self.assertEqual(checkpoint_json.json()["result"]["status"], "JOURNAL_CHECKPOINT_READY")
        self.assertFalse(checkpoint_json.json()["can_place_order_from_this_mcp"])
        self.assertEqual(checkpoint_html.status_code, 200)
        self.assertIn("Journal Checkpoint", checkpoint_html.text)
        self.assertIn("live_review_cycle", checkpoint_html.text)
