from __future__ import annotations

from typing import Any

from app.version import BUILD_VERSION


class DebugValidationService:
    def __init__(self, container: Any):
        self.container = container

    async def full_health(self, listed_tools: list[str], expected_build_version: str | None = None) -> dict[str, Any]:
        build_matches = expected_build_version in {None, "", BUILD_VERSION}
        return {
            "status": "OK" if build_matches else "BUILD_MISMATCH",
            "service": self.container.settings.app_name,
            "build_version": BUILD_VERSION,
            "expected_build_version": expected_build_version,
            "build_matches_expected": build_matches,
            "tool_count": len(listed_tools),
            "required_tools": self._required_tool_status(listed_tools),
            "schema_versions": {
                "evidence_packet": "1.0",
                "scan_schema": "debug_static_v1",
                "scorecard_model": "research_report_v1_preview",
                "small_account_friction": "friction_adjusted_v1",
                "setup_memory": "setup_fingerprint_v1",
                "market_harvest": "review_harvest_v1",
                "session_loop": "session_loop_v1",
                "ops_command_center": "command_center_v2",
                "manual_preflight_ticket": "manual_preflight_v1",
                "paper_option_ledger": "paper_option_ledger_v1",
                "morning_autopilot": "morning_autopilot_v2",
                "live_review_cycle": "live_review_cycle_v2",
                "journal_checkpoint": "journal_checkpoint_v1",
                "journal_checkpoint_restore": "journal_checkpoint_restore_v1",
                "manual_trade_desk": "manual_trade_desk_v2",
                "manual_snapshot_form": "manual_snapshot_form_v1",
                "manual_option_position_watch": "manual_option_position_watch_v1",
                "market_open_observer": "market_open_observer_v1",
                "observer_followup": "observer_followup_v1",
                "manual_broker_action": "manual_broker_action_v1",
                "trading_day_launch": "trading_day_launch_v2",
                "tomorrow_operator_brief": "tomorrow_operator_brief_v1",
                "go_live_rehearsal": "go_live_rehearsal_v1",
                "trading_day_heartbeat": "trading_day_heartbeat_v1",
                "day_monitor": "day_monitor_v1",
                "trading_day_alerts": "trading_day_alerts_v1",
                "session_risk_guard": "session_risk_guard_v1",
                "failure_mode_audit": "failure_mode_audit_v1",
                "options_data_status": "options_data_status_v1",
                "real_money_options_truth_gate": "real_money_options_truth_gate_v1",
                "truth_source_status": "truth_source_status_v1",
                "market_data_health": "market_data_health_v1",
                "catalyst_context": "catalyst_context_v1",
                "autonomous_morning_scan": "autonomous_morning_scan_v1",
                "event_volatility": "event_volatility_v1",
                "event_radar": "event_radar_v1",
                "broad_opportunity_scan": "broad_opportunity_scan_v1",
                "data_truth_cockpit": "data_truth_cockpit_v1",
                "system_communication_audit": "system_communication_audit_v1",
                "strategy_module_registry": "strategy_module_registry_v1",
                "shared_intelligence": "shared_intelligence_v1",
                "autonomous_launch_decision": "autonomous_launch_decision_v1",
                "real_cash_proof_gate": "real_cash_proof_gate_v1",
                "broker_proof_bridge": "broker_proof_bridge_v1",
                "autonomous_control_state": "autonomous_control_state_v1",
                "trading_monster_dashboard": "trading_monster_dashboard_v1",
                "cross_asset_capital_plan": "cross_asset_capital_plan_v1",
                "full_market_visibility": "full_market_visibility_v1",
                "listed_equity_master_universe": "listed_equity_master_universe_v1",
                "event_volatility_war_room": "event_volatility_war_room_v1",
                "loss_review_reassessment": "loss_review_reassessment_v1",
                "broker_executor_bridge": "broker_executor_bridge_v1",
                "robinhood_crypto_universe": "robinhood_crypto_universe_v1",
                "crypto_live_test_gate": "crypto_live_test_gate_v1",
                "crypto_live_test_report": "crypto_live_test_report_v1",
                "crypto_autonomous_cycle": "crypto_autonomous_cycle_v1",
            },
            "debug_routes": [
                "/health/full",
                "/debug/tool-manifest",
                "/debug/scan-schema",
                "/ops/morning-autopilot",
                "/ops/live-review-cycle",
                "/ops/market-open-observer",
                "/ops/observer-followup",
                "/ops/trading-day-launch",
                "/ops/tomorrow-brief",
                "/ops/go-live-rehearsal",
                "/ops/day-heartbeat",
                "/ops/day-monitor",
                "/ops/day-alerts",
                "/ops/autonomous-morning-scan",
                "/ops/event-radar",
                "/ops/event-volatility-playbook",
                "/ops/event-volatility-scan",
                "/ops/broad-opportunity-scan",
                "/ops/data-truth-cockpit",
                "/ops/system-communication-audit",
                "/ops/strategy-modules",
                "/ops/shared-intelligence",
                "/ops/autonomous-launch-decision",
                "/ops/autonomy-control",
                "/ops/trading-monster-dashboard",
                "/ops/real-cash-proof-gate",
                "/ops/broker-proof-bridge",
                "/risk/capital-plan",
                "/risk/loss-reassessment",
                "/ops/full-market-visibility",
                "/ops/listed-equity-universe",
                "/ops/event-war-room",
                "/ops/broker-executor-bridge",
                "/paper/options/summary",
                "/paper/options/watch",
                "/journal/checkpoint",
                "/trade/manual-desk",
                "/trade/manual-form",
                "/trade/manual-action",
                "/trade/pending-recheck",
                "/options/data-status",
                "/truth/source-status",
                "/market/data-health",
                "/research/catalyst-context",
                "/risk/session",
                "/risk/failure-mode-audit",
                "/crypto/universe",
                "/crypto/autonomous-cycle",
                "/crypto/live-test",
                "/crypto/test-report",
            ],
            "readiness": {
                "version_endpoint": True,
                "tools_endpoint": True,
                "blueprint_routes": True,
                "evidence_packet_routes": True,
                "scan_rows_include_evidence_packet": True,
                "scan_rows_include_evidence_scorecard": True,
                "options_review_includes_friction_score": True,
                "options_review_includes_setup_memory": True,
                "market_readiness_route": True,
                "review_harvest_route": True,
                "session_playbook_route": True,
                "harvest_followup_route": True,
                "ops_command_center_route": True,
                "morning_autopilot_route": True,
                "live_review_cycle_route": True,
                "market_open_observer_route": True,
                "observer_followup_route": True,
                "trading_day_launch_route": True,
                "tomorrow_operator_brief_route": True,
                "go_live_rehearsal_route": True,
                "trading_day_heartbeat_route": True,
                "day_monitor_route": True,
                "trading_day_alerts_route": True,
                "autonomous_morning_scan_route": True,
                "event_radar_route": True,
                "event_volatility_playbook_route": True,
                "event_volatility_scan_route": True,
                "broad_opportunity_scan_route": True,
                "data_truth_cockpit_route": True,
                "system_communication_audit_route": True,
                "strategy_module_registry_route": True,
                "shared_intelligence_route": True,
                "autonomous_launch_decision_route": True,
                "real_cash_proof_gate_route": True,
                "broker_proof_bridge_route": True,
                "autonomy_control_route": True,
                "trading_monster_dashboard_route": True,
                "cross_asset_capital_plan_route": True,
                "full_market_visibility_route": True,
                "listed_equity_master_universe_route": True,
                "event_war_room_route": True,
                "loss_reassessment_route": True,
                "broker_executor_bridge_route": True,
                "manual_preflight_route": True,
                "paper_option_ledger_routes": True,
                "paper_option_position_watch_route": True,
                "journal_checkpoint_route": True,
                "journal_checkpoint_restore": True,
                "manual_trade_desk_route": True,
                "manual_snapshot_form_route": True,
                "manual_broker_action_route": True,
                "pending_recheck_route": True,
                "options_data_status_route": True,
                "truth_source_status_route": True,
                "market_data_health_route": True,
                "catalyst_context_route": True,
                "session_risk_guard_route": True,
                "failure_mode_audit_route": True,
                "crypto_universe_route": True,
                "crypto_autonomous_cycle_route": True,
                "crypto_live_test_gate_route": True,
                "crypto_live_test_report_route": True,
            },
            "safety": self._safety(),
            "options_data_status": self.container.options.options_data_status(),
            "truth_source_status_schema_preview": self._truth_source_status_schema_preview(),
        }

    async def tool_manifest(self, listed_tools: list[Any]) -> dict[str, Any]:
        tools = []
        for tool in listed_tools:
            name = getattr(tool, "name", str(tool))
            tools.append(
                {
                    "name": name,
                    "category": self._category(name),
                    "write_or_broker_action": False,
                    "can_place_order": False,
                    "notes": self._tool_notes(name),
                }
            )
        return {
            "status": "TOOL_MANIFEST_READY",
            "build_version": BUILD_VERSION,
            "tool_count": len(tools),
            "tools": tools,
            "required_tools": self._required_tool_status([tool["name"] for tool in tools]),
            "safety": self._safety(),
        }

    def scan_schema_example(self, expected_build_version: str | None = None) -> dict[str, Any]:
        build_matches = expected_build_version in {None, "", BUILD_VERSION}
        example = {
            "ticker": "EXAMPLE",
            "status": "CANDIDATE",
            "score": 76.0,
            "confidence": "low-medium",
            "direction": "short",
            "setup_type": "scalp_review",
            "quality_gates": {
                "stock_setup_quality": "VALID_CANDIDATE",
                "options_chain_quality": "NOT_VALIDATED",
                "execution_quality": "REVIEW_ONLY_NO_EXECUTION",
            },
            "key_signals": {
                "score": 76.0,
                "confidence": "low-medium",
                "direction": "short",
                "trend_pct": -0.017,
                "recent_trend_pct": -0.004,
                "above_vwap": False,
                "below_vwap": True,
                "vwap": 100.25,
                "relative_volume": 0.82,
                "relative_volume_status": "same_time_of_day",
                "relative_strength": {
                    "status": "available",
                    "benchmark": "SPY",
                    "direction": "short",
                    "benchmark_trend_pct": -0.004,
                    "benchmark_recent_trend_pct": -0.001,
                    "excess_trend_pct": -0.013,
                    "excess_recent_trend_pct": -0.003,
                    "label": "leading_spy",
                    "note": "Diagnostic only until backtested; sector-relative strength remains planned.",
                },
                "pct_change_vs_previous_close": -0.011,
                "scan_profile": "scalp",
                "evidence_scorecard": {
                    "model": "research_report_v1_preview",
                    "active_scanner_score": 76.0,
                    "preview_base_score": 42.0,
                    "preview_penalty_score": 3.0,
                    "preview_final_score": 39.0,
                    "modules": [
                        {"name": "volume_liquidity", "points": 6.0, "max_points": 17, "reason": "Participation is below preferred scalp floor."},
                        {"name": "structure_vwap", "points": 18.0, "max_points": 23, "reason": "Direction aligns with VWAP."},
                        {"name": "relative_strength_vs_spy", "points": 14.0, "max_points": 14, "reason": "SPY-relative strength diagnostic is leading_spy; sector-relative strength still planned."},
                        {"name": "volatility_expansion", "points": 8.0, "max_points": 10, "reason": "Trend/recent-trend expansion proxy."},
                        {"name": "order_flow_or_proxy", "points": 10.0, "max_points": 12, "reason": "Bar-pressure proxy; no L2/order-flow data in this build."},
                    ],
                    "penalties": [
                        {"name": "low_relative_volume", "penalty": 3.0, "reason": "RVOL is below preferred scalp floor; keep urgency cautious."}
                    ],
                    "missing_or_planned_modules": [
                        "catalyst_context",
                        "sector_relative_strength",
                        "higher_timeframe_context",
                        "full_l2_order_flow",
                        "options_suitability_until_options_review",
                    ],
                },
            },
            "evidence_packet": {
                "schema_version": "1.0",
                "packet_type": "compact_scan_evidence",
                "build_version": BUILD_VERSION,
                "provider_lineage": {
                    "quote_provider": "finnhub",
                    "quote_freshness_status": "LAST_REGULAR_SESSION_ACCEPTED",
                    "quote_derived_from_candles": False,
                    "candle_provider": "yfinance",
                    "candle_freshness_status": "LAST_REGULAR_SESSION_ACCEPTED",
                    "candle_count": 390,
                },
                "data_confidence": {
                    "score": 69,
                    "status": "MEDIUM",
                    "penalties": [
                        {"flag": "relative_volume_below_preferred_floor", "penalty": 6},
                        {"flag": "catalyst_context_missing", "penalty": 10},
                        {"flag": "sector_relative_strength_missing", "penalty": 5},
                        {"flag": "l2_order_flow_missing", "penalty": 5},
                    ],
                },
                "data_flags": [
                    "relative_volume_below_preferred_floor",
                    "catalyst_context_missing",
                    "sector_relative_strength_missing",
                    "l2_order_flow_missing",
                ],
                "missing_or_planned_modules": [
                    "catalyst_context",
                    "sector_relative_strength",
                    "higher_timeframe_context",
                    "full_l2_order_flow",
                    "options_suitability_until_options_review",
                ],
                "replay_fields_present": {
                    "quote_summary": True,
                    "candle_summary": True,
                    "key_signals": True,
                    "evidence_scorecard": True,
                    "quality_gates": True,
                },
            },
            "missing_modules": [
                "catalyst_context",
                "sector_relative_strength",
                "higher_timeframe_context",
                "full_l2_order_flow",
                "options_suitability_until_options_review",
            ],
            "penalty_reasons": [
                "RVOL is below preferred scalp floor; keep urgency cautious.",
                "Catalyst context missing.",
                "Sector-relative strength missing; SPY-relative strength diagnostic is available.",
                "Full L2/order-flow feed missing.",
            ],
            "confidence_band": "MEDIUM",
            "known_blindspots": [
                "Automated options truth requires MarketData/Tradier configuration; otherwise use broker snapshot validation.",
                "No structured catalyst/news feed in this build.",
                "No sector-relative strength module yet; SPY-relative strength is diagnostic only until backtested.",
                "No L2/order-flow feed yet.",
            ],
            "why_not_ranked": "Static schema example only; not a live candidate and not eligible for ranking.",
            "review_only": True,
            "order_allowed": False,
        }
        return {
            "status": "SCAN_SCHEMA_READY" if build_matches else "BUILD_MISMATCH",
            "build_version": BUILD_VERSION,
            "expected_build_version": expected_build_version,
            "build_matches_expected": build_matches,
            "schema_version": "debug_static_v1",
            "example_candidate": example,
            "options_review_schema_preview": self._options_review_schema_preview(),
            "options_data_status_schema_preview": self.container.options.options_data_status(),
            "truth_source_status_schema_preview": self._truth_source_status_schema_preview(),
            "market_data_health_schema_preview": self._market_data_health_schema_preview(),
            "catalyst_context_schema_preview": self._catalyst_context_schema_preview(),
            "autonomous_morning_scan_schema_preview": self._autonomous_morning_scan_schema_preview(),
            "setup_memory_schema_preview": self._setup_memory_schema_preview(),
            "review_harvest_schema_preview": self._review_harvest_schema_preview(),
            "session_playbook_schema_preview": self._session_playbook_schema_preview(),
            "harvest_followup_schema_preview": self._harvest_followup_schema_preview(),
            "ops_command_center_schema_preview": self._ops_command_center_schema_preview(),
            "trading_day_launch_schema_preview": self._trading_day_launch_schema_preview(),
            "tomorrow_operator_brief_schema_preview": self._tomorrow_operator_brief_schema_preview(),
            "go_live_rehearsal_schema_preview": self._go_live_rehearsal_schema_preview(),
            "trading_day_heartbeat_schema_preview": self._trading_day_heartbeat_schema_preview(),
            "day_monitor_schema_preview": self._day_monitor_schema_preview(),
            "trading_day_alerts_schema_preview": self._trading_day_alerts_schema_preview(),
            "morning_autopilot_schema_preview": self._morning_autopilot_schema_preview(),
            "live_review_cycle_schema_preview": self._live_review_cycle_schema_preview(),
            "market_open_observer_schema_preview": self._market_open_observer_schema_preview(),
            "observer_followup_schema_preview": self._observer_followup_schema_preview(),
            "manual_preflight_schema_preview": self._manual_preflight_schema_preview(),
            "manual_trade_desk_schema_preview": self._manual_trade_desk_schema_preview(),
            "manual_snapshot_form_schema_preview": self._manual_snapshot_form_schema_preview(),
            "manual_option_position_watch_schema_preview": self._manual_option_position_watch_schema_preview(),
            "manual_broker_action_schema_preview": self._manual_broker_action_schema_preview(),
            "paper_option_ledger_schema_preview": self._paper_option_ledger_schema_preview(),
            "session_risk_guard_schema_preview": self._session_risk_guard_schema_preview(),
            "journal_checkpoint_schema_preview": self._journal_checkpoint_schema_preview(),
            "journal_checkpoint_restore_schema_preview": self._journal_checkpoint_restore_schema_preview(),
            "safety": self._safety(),
        }

    def _options_review_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "REVIEW_ONLY_OPTIONS_READY",
            "small_account_review": {
                "status": "SMALL_ACCOUNT_SCALP_ACCEPTABLE",
                "priority_score": 86.0,
                "friction_adjusted_score": 86.0,
                "friction_band": "LOW_FRICTION",
                "friction_adjusted_review": {
                    "score": 86.0,
                    "band": "LOW_FRICTION",
                    "penalties": [
                        {"name": "spread_wide", "penalty": 10.0, "reason": "Spread is wider than preferred and needs limit-order discipline."},
                        {"name": "cheap_contract_tick_risk", "penalty": 4.0, "reason": "Very cheap contracts can have misleading percentage spreads and fast premium decay."},
                    ],
                    "components": {
                        "bid": 0.07,
                        "ask": 0.08,
                        "spread_pct": 0.12,
                        "absolute_spread": 0.01,
                        "estimated_round_trip_slippage_dollars": 1.0,
                        "slippage_pct_of_max_loss": 0.125,
                        "volume": 3500,
                        "open_interest": 8000,
                        "days_to_expiration": 3,
                        "max_loss_dollars": 8.0,
                    },
                },
            },
            "notes": "Static schema preview only. It does not run an options review or create a trade plan.",
        }

    def _truth_source_status_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "TRUTH_SOURCE_STATUS_READY",
            "schema_version": "truth_source_status_v1",
            "market_data": {
                "provider": "finnhub",
                "feed_type": "equity_quote_and_candle_review",
                "cash_ready": True,
            },
            "options_data": {
                "schema_version": "options_data_status_v1",
                "real_money_options_truth_status": "BROKER_SNAPSHOT_REQUIRED",
            },
            "cash_readiness": {
                "cash_ready": False,
                "reason": "Real-money readiness still requires in-session market health, catalyst context, and fresh options truth or broker snapshot.",
            },
            "blocked_for_cash_without": [
                "fresh market data health check",
                "fresh catalyst context",
                "REAL_MONEY_OPTIONS_TRUTH_READY or fresh broker snapshot",
                "manual risk guard",
                "manual approval outside MCP",
            ],
            "notes": "Static truth-source preview only. It does not run a scan or create a trade plan.",
        }

    def _market_data_health_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "MARKET_DATA_HEALTHY",
            "schema_version": "market_data_health_v1",
            "provider": "finnhub",
            "healthy_count": 1,
            "degraded_count": 0,
            "rows": [
                {
                    "ticker": "EXAMPLE",
                    "status": "HEALTHY",
                    "quote_age_seconds": 5.0,
                    "candle_age_seconds": 120.0,
                    "blocking_reasons": [],
                }
            ],
            "cash_ready": True,
            "notes": "Static market-health preview only. The live route checks quote and candle freshness without broker action.",
        }

    def _catalyst_context_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "CATALYST_CONTEXT_CLEAR",
            "schema_version": "catalyst_context_v1",
            "ticker": "EXAMPLE",
            "news_count": 2,
            "earnings_count": 0,
            "risk_items": [],
            "blocking_reasons": [],
            "cash_ready": True,
            "notes": "Static catalyst preview only. The live route fails closed if catalyst data is missing or risky.",
        }

    def _autonomous_morning_scan_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "AUTONOMOUS_ACTIVE_SCAN_RUNNING",
            "schema_version": "autonomous_morning_scan_v1",
            "phase": {"phase": "active", "forced": False},
            "truth_source": {"status": "TRUTH_SOURCE_STATUS_READY"},
            "market_data_health": {"status": "MARKET_DATA_HEALTHY", "healthy_count": 8, "degraded_count": 0},
            "catalyst_context": {
                "checked_count": 5,
                "clear_count": 5,
                "blocked_or_unavailable_count": 0,
                "blocks": [],
            },
            "heartbeat": {"status": "HEARTBEAT_NO_TRADE_PLAN"},
            "cash_readiness": {
                "truth_cash_ready": False,
                "market_data_cash_ready": True,
                "catalyst_blocks_clear": True,
                "manual_broker_snapshot_still_required_for_options": True,
                "autonomous_cash_trading_allowed": False,
            },
            "next_refresh_seconds": 300,
            "hard_stops": [
                "No broker order can be placed, modified, submitted, simulated, or canceled by this MCP.",
                "No options cash review without fresh broker-visible bid, ask, volume, open interest, DTE, strike, and max loss.",
            ],
            "notes": "Static autonomous-morning preview only. The live route runs one review-only cycle and cannot execute broker actions.",
        }

    def _setup_memory_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "SETUP_MEMORY_READY",
            "memory_signal": "NO_MEMORY_YET",
            "fingerprint": {
                "setup_key": "setup_type:scalp_review|direction:short|vwap_state:below|relative_strength_label:mixed_vs_spy|rvol_bucket:soft|friction_band:MANAGEABLE_FRICTION|dte_bucket:2_3dte|spread_bucket:wide|max_loss_bucket:small",
                "dimensions": {
                    "setup_type": "scalp_review",
                    "direction": "short",
                    "vwap_state": "below",
                    "relative_strength_label": "mixed_vs_spy",
                    "rvol_bucket": "soft",
                    "friction_band": "MANAGEABLE_FRICTION",
                    "dte_bucket": "2_3dte",
                    "spread_bucket": "wide",
                    "max_loss_bucket": "small",
                },
                "tags": ["rvol_soft", "wide_spread"],
            },
            "similar_review_summary": {"sample_size": 0},
            "similar_lesson_summary": {"sample_size": 0},
            "notes": "Static setup-memory schema preview only. It does not run a scan or create a trade plan.",
        }

    def _review_harvest_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "REVIEW_HARVEST_READY",
            "schema_version": "review_harvest_v1",
            "ranked_candidates": [
                {
                    "ticker": "EXAMPLE",
                    "status": "REVIEW_ONLY_OPTIONS_READY",
                    "direction": "short",
                    "score": 86.0,
                    "priority_score": 82.0,
                    "friction_adjusted_score": 84.0,
                    "contract": "EXAMPLE260612P00100000",
                    "ask": 0.42,
                    "max_loss_dollars": 42.0,
                    "memory_signal": "NO_MEMORY_YET",
                }
            ],
            "followup_checks": [
                {
                    "ticker": "EXAMPLE",
                    "direction": "short",
                    "entry_reference": 100.0,
                    "check_after_minutes": [15, 30, 60],
                }
            ],
            "notes": "Static harvest schema preview only. It does not run a live scan or create a trade plan.",
        }

    def _session_playbook_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "SESSION_PLAYBOOK_READY",
            "schema_version": "session_loop_v1",
            "session_blocks": [
                {"label": "Pre-market setup", "central_time": "07:45-08:25"},
                {"label": "Opening stabilization", "central_time": "08:30-08:50"},
                {"label": "First review harvest", "central_time": "08:50-10:15"},
                {"label": "Afternoon decision window", "central_time": "12:30-14:15"},
                {"label": "After-action learning", "central_time": "After each review and after close"},
            ],
            "manual_trade_gate": [
                "Build and safety confirmed.",
                "Harvest candidate is REVIEW_ONLY_OPTIONS_READY.",
                "Small-account gate is SMALL_ACCOUNT_SCALP_ACCEPTABLE.",
                "Broker-visible option snapshot matches or improves the MCP quote.",
            ],
            "notes": "Static playbook schema preview only. It cannot create a trade plan or broker action.",
        }

    def _harvest_followup_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "HARVEST_FOLLOWUP_COMPLETE",
            "schema_version": "session_loop_v1",
            "outcomes": [
                {
                    "ticker": "EXAMPLE",
                    "verdict": "HELPED",
                    "current_return_pct": 0.004,
                    "max_favorable_excursion": 0.007,
                    "max_adverse_excursion": -0.001,
                }
            ],
            "classifications": [
                {
                    "ticker": "EXAMPLE",
                    "classification": "GOOD_SIGNAL",
                    "lesson_tags": ["wide_spread"],
                }
            ],
            "notes": "Static follow-up schema preview only. It does not run market data or apply rule changes.",
        }

    def _ops_command_center_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "READY_FOR_HARVEST",
            "schema_version": "command_center_v2",
            "latest": {
                "market_readiness": {"status": "MARKET_REVIEW_READY"},
                "review_harvest": None,
                "harvest_followup": None,
                "learning_summary": None,
                "session_risk_guard": {"status": "SESSION_RISK_CLEAR"},
            },
            "next_action": {
                "label": "Run review harvest.",
                "endpoint": "/ops/review-harvest",
            },
            "action_links": {
                "market_readiness": "/ops/market-readiness",
                "review_harvest": "/ops/review-harvest",
                "harvest_followup": "/ops/harvest-followup",
                "session_risk": "/risk/session",
                "learning_dashboard": "/learning/dashboard",
            },
            "notes": "Static command-center schema preview only. It reads loop state and does not run scans.",
        }

    def _trading_day_launch_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "LAUNCH_START_HERE",
            "schema_version": "trading_day_launch_v2",
            "next_action": "Start with health/build checks, then market readiness and market-open observer.",
            "launch_sequence": [
                {"phase": "Build and safety", "primary_link": "/health/full"},
                {"phase": "Session risk", "primary_link": "/risk/session"},
                {"phase": "Opening observation", "primary_link": "/ops/market-open-observer"},
                {"phase": "Live review cycle", "primary_link": "/ops/live-review-cycle"},
                {"phase": "Manual broker inspection", "primary_link": "/trade/manual-desk"},
                {"phase": "Manual action journal", "primary_link": "/trade/manual-action"},
                {"phase": "Learning and checkpoint", "primary_link": "/journal/checkpoint"},
            ],
            "absolute_no_trade_rules": [
                "No market orders.",
                "No stock-setup-only trades.",
                "No stale pending buy trusted after 60 seconds without recheck.",
                "No new manual idea while session risk is SESSION_RISK_BLOCKED.",
                "No broker action from this MCP.",
            ],
            "notes": "Static launch checklist preview only. The live tool maps safe next actions and cannot execute broker actions.",
        }

    def _tomorrow_operator_brief_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "OPERATOR_READY_TO_START",
            "schema_version": "tomorrow_operator_brief_v1",
            "session_risk_guard": self._session_risk_guard_schema_preview(),
            "morning_sequence": [
                {"step": "1. Confirm deployment", "link": "/health/full"},
                {"step": "2. Open launch page", "link": "/ops/trading-day-launch"},
                {"step": "3. Run morning autopilot", "link": "/ops/morning-autopilot"},
                {"step": "4. Leave day monitor open", "link": "/ops/day-monitor"},
            ],
            "chatgpt_connector_fallback": {
                "validation_urls": ["/version", "/tools", "/health/full", "/debug/scan-schema"],
                "short_status": "Use public endpoints if the callable namespace is not exposed.",
            },
            "manual_trade_gate": [
                "Session risk guard is not SESSION_RISK_BLOCKED.",
                "Live review cycle status is LIVE_CYCLE_CANDIDATES_READY.",
                "Manual trade desk returns MANUAL_TRADE_DESK_READY.",
            ],
            "absolute_no_trade_rules": [
                "No broker action from this MCP.",
                "No market orders.",
                "No stock-setup-only trades.",
            ],
            "notes": "Static operator brief preview only. The live route summarizes safe pages and cannot execute broker actions.",
        }

    def _go_live_rehearsal_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "GO_LIVE_REHEARSAL_READY",
            "schema_version": "go_live_rehearsal_v1",
            "operator_brief": {
                "status": "OPERATOR_READY_TO_START",
                "session_risk_status": "SESSION_RISK_CLEAR",
                "paper_open_count": 0,
            },
            "required_live_urls": [
                {"label": "Root operator brief", "url": "/"},
                {"label": "Version", "url": "/version"},
                {"label": "Tools", "url": "/tools"},
                {"label": "Full health", "url": "/health/full"},
                {"label": "Go-live rehearsal", "url": "/ops/go-live-rehearsal"},
            ],
            "tomorrow_open_tabs": [
                {"label": "Operator brief", "url": "/ops/tomorrow-brief"},
                {"label": "Day monitor", "url": "/ops/day-monitor"},
                {"label": "Day alerts", "url": "/ops/day-alerts"},
            ],
            "blocking_reasons": [],
            "warnings": [],
            "notes": "Static go-live rehearsal preview only. The live tool checks workflow readiness and cannot execute broker actions.",
        }

    def _trading_day_heartbeat_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "HEARTBEAT_NO_TRADE_PLAN",
            "schema_version": "trading_day_heartbeat_v1",
            "phase": {
                "phase": "active",
                "forced": True,
                "now_utc": "2026-06-10T15:00:00Z",
                "now_et": "2026-06-10T11:00:00-04:00",
            },
            "operation": "live_review_cycle",
            "operation_status": "LIVE_CYCLE_NO_ELIGIBLE_CANDIDATES",
            "next_refresh_seconds": 300,
            "pending_recheck_required": False,
            "absolute_no_trade_rules": [
                "No market orders.",
                "No broker action from this MCP.",
                "No trade from the heartbeat alone; use live review cycle plus manual trade desk.",
            ],
            "notes": "Static heartbeat schema preview only. The live tool runs one safe cadence step and cannot execute broker actions.",
        }

    def _day_monitor_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "DAY_MONITOR_READY",
            "schema_version": "day_monitor_v1",
            "route": "/ops/day-monitor",
            "wraps": "run_trading_day_heartbeat",
            "auto_refresh_default": True,
            "min_refresh_seconds": 60,
            "max_refresh_seconds": 1800,
            "notes": "Static monitor preview only. The live route auto-refreshes the review-only heartbeat page while the browser tab is open.",
        }

    def _trading_day_alerts_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "ALERTS_MANUAL_REVIEW_READY",
            "schema_version": "trading_day_alerts_v1",
            "top_level": "REVIEW",
            "alert_count": 1,
            "alerts": [
                {
                    "level": "REVIEW",
                    "type": "MANUAL_REVIEW_READY",
                    "title": "Heartbeat found a candidate ready for manual broker inspection",
                    "next_action": "Use manual trade desk with broker-visible fields.",
                    "link": "/trade/manual-desk",
                }
            ],
            "notes": "Static alerts preview only. The live tool summarizes review-only journal events and cannot execute broker actions.",
        }

    def _morning_autopilot_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "AUTOPILOT_READY_FOR_HARVEST",
            "schema_version": "morning_autopilot_v2",
            "readiness": {
                "status": "MARKET_REVIEW_READY",
                "candidate_count": 3,
                "valid_row_count": 20,
                "quote_problem_count": 0,
            },
            "paper_ledger": {
                "status": "PAPER_LEDGER_READY",
                "entry_count": 2,
                "open_count": 0,
                "closed_count": 2,
                "total_pnl_dollars": 4.0,
            },
            "session_risk_guard": self._session_risk_guard_schema_preview(),
            "next_action": "Run review harvest, then options-review only valid directional stock candidates.",
            "action_links": {
                "market_readiness": "/ops/market-readiness",
                "review_harvest": "/ops/review-harvest",
                "paper_ledger": "/paper/options/summary",
            },
            "notes": "Static autopilot schema preview only. The live tool summarizes readiness and the review loop but cannot execute broker actions.",
        }

    def _live_review_cycle_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "LIVE_CYCLE_CANDIDATES_READY",
            "schema_version": "live_review_cycle_v2",
            "readiness": {
                "status": "MARKET_REVIEW_READY",
                "valid_row_count": 20,
                "quote_problem_count": 0,
            },
            "harvest": {
                "status": "REVIEW_HARVEST_READY",
                "reviewed_count": 8,
                "eligible_count": 2,
                "watch_only_count": 6,
            },
            "ranked_candidates": [
                {
                    "ticker": "EXAMPLE",
                    "status": "REVIEW_ONLY_OPTIONS_READY",
                    "small_account_review": {"status": "SMALL_ACCOUNT_SCALP_ACCEPTABLE", "priority_score": 86},
                    "selected_contract": {"contract_symbol": "EXAMPLE260612P00100000", "ask": 0.42, "max_loss_dollars": 42.0},
                }
            ],
            "session_risk_guard": self._session_risk_guard_schema_preview(),
            "next_action": "Manually inspect the top candidate in broker, then run manual preflight with broker-visible bid/ask/volume/OI.",
            "manual_preflight_required": True,
            "notes": "Static live-cycle schema preview only. The live tool can run readiness and harvest but cannot execute broker actions.",
        }

    def _market_open_observer_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "OBSERVER_STOCK_CANDIDATES",
            "schema_version": "market_open_observer_v1",
            "cadence_minutes": 5,
            "candidate_count": 2,
            "pass_count": 18,
            "evidence_packet_count": 20,
            "evidence_summary": {
                "decision_counts": {"CANDIDATE": 2, "PASS": 18},
                "data_confidence_counts": {"HIGH": 14, "MEDIUM": 6},
                "top_data_flags": {"pass_first_decision": 18, "catalyst_context_missing": 20},
            },
            "candidate_observations": [
                {
                    "ticker": "EXAMPLE",
                    "direction": "short",
                    "score": 76,
                    "relative_volume": 1.4,
                    "vwap_state": "below",
                    "data_confidence": "HIGH",
                }
            ],
            "delta_vs_previous_observer": {
                "status": "OBSERVER_DELTA_READY",
                "new_candidate_tickers": ["EXAMPLE"],
                "dropped_candidate_tickers": [],
                "persistent_candidate_tickers": [],
            },
            "next_action": "After spreads stabilize, run live review cycle; only continue if stock setup and SMALL_ACCOUNT_SCALP_ACCEPTABLE both pass.",
            "notes": "Static observer schema preview only. The live tool records scan evidence and cannot options-review, rank contracts, or execute broker actions.",
        }

    def _observer_followup_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "OBSERVER_FOLLOWUP_COMPLETE",
            "schema_version": "observer_followup_v1",
            "source_observation_count": 3,
            "items_checked": 12,
            "include_passes": True,
            "missed_move_count": 1,
            "good_pass_count": 5,
            "outcomes": [
                {
                    "ticker": "EXAMPLE",
                    "source_bucket": "pass",
                    "current_return_pct": 0.004,
                    "max_favorable_excursion": 0.007,
                    "verdict": "HELPED",
                }
            ],
            "classifications": [
                {
                    "ticker": "EXAMPLE",
                    "classification": "MISSED_MOVE",
                    "lesson_tags": ["low_relative_volume"],
                    "reason": "The pass/reject item later had enough favorable excursion to study.",
                }
            ],
            "next_action": "Review missed-move labels and rule proposals before changing any active gate.",
            "notes": "Static follow-up schema preview only. The live tool grades observer evidence and cannot execute broker actions.",
        }

    def _manual_preflight_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "MANUAL_PREFLIGHT_READY",
            "schema_version": "manual_preflight_v1",
            "selected_contract": {
                "contract_symbol": "EXAMPLE260612P00100000",
                "bid": 0.4,
                "ask": 0.42,
                "spread_pct": 0.0488,
                "volume": 1000,
                "open_interest": 2500,
                "days_to_expiration": 3,
                "max_loss_dollars": 42.0,
            },
            "manual_ticket": {
                "order_type": "limit_only",
                "max_review_ask": 0.42,
                "quantity": 1,
                "mcp_can_execute": False,
            },
            "notes": "Static preflight schema preview only. It validates broker-visible snapshots and cannot execute.",
        }

    def _manual_trade_desk_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "MANUAL_TRADE_DESK_READY",
            "schema_version": "manual_trade_desk_v2",
            "preflight": self._manual_preflight_schema_preview(),
            "session_risk_guard": self._session_risk_guard_schema_preview(),
            "blocking_reasons": [],
            "warnings": [],
            "paper_entry_request": {
                "endpoint": "/paper/options/entry",
                "payload": {
                    "fill_price": 0.42,
                    "quantity": 1,
                    "underlying_price": 100.0,
                },
            },
            "checkpoint_request": {"endpoint": "/journal/checkpoint?limit=500&format=json"},
            "next_steps": [
                "Confirm broker-visible fields still match.",
                "Use limit-only discipline.",
                "Log paper/manual fill for learning.",
                "Export checkpoint after the decision.",
            ],
            "notes": "Static trade-desk schema preview only. It cannot execute broker actions.",
        }

    def _manual_snapshot_form_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "MANUAL_SNAPSHOT_FORM_READY",
            "schema_version": "manual_snapshot_form_v1",
            "route": "/trade/manual-form",
            "submits_to": "/trade/manual-desk",
            "required_fields": [
                "ticker",
                "contract_symbol",
                "direction",
                "bid",
                "ask",
                "volume",
                "open_interest",
                "dte",
                "strike",
            ],
            "optional_fields": [
                "underlying_price",
                "underlying_vwap",
                "account_value",
                "max_contract_price",
                "max_open_positions",
            ],
            "notes": "Static form preview only. The live route helps enter broker-visible fields and cannot execute broker actions.",
        }

    def _manual_option_position_watch_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "POSITION_PROFIT_REVIEW",
            "schema_version": "manual_option_position_watch_v1",
            "ticker": "SOFI",
            "direction": "put",
            "contract_symbol": "SOFI260612P00015000",
            "entry_price": 0.08,
            "current_mark": 0.12,
            "return_pct": 0.5,
            "pnl_dollars": 4.0,
            "next_action": "Large option gain; consider manual profit-taking or tight stop discipline.",
            "close_request": {
                "endpoint": "/paper/options/close",
                "exit_price": 0.12,
                "exit_reason": "profit_target",
            },
            "notes": "Static position-watch preview only. The live route reviews an open manual/paper option and cannot close broker positions.",
        }

    def _manual_broker_action_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "MANUAL_ACTION_PENDING_RECHECK_REQUIRED",
            "schema_version": "manual_broker_action_v1",
            "ticker": "EXAMPLE",
            "contract_symbol": "EXAMPLE260612P00100000",
            "action_type": "pending_buy",
            "order_status": "queued",
            "side": "buy",
            "direction": "put",
            "limit_price": 0.42,
            "submitted_at": "2026-06-10T14:30:00+00:00",
            "pending_buy": True,
            "pending_buy_recheck_seconds": 60,
            "recheck_request": {
                "tool": "review_pending_buy_order",
                "endpoint": "/trade/pending-recheck",
                "payload": {
                    "ticker": "EXAMPLE",
                    "submitted_at": "2026-06-10T14:30:00+00:00",
                    "limit_price": 0.42,
                    "is_options_order": True,
                    "direction": "put",
                    "mode": "scalp_review",
                },
            },
            "notes": "Static manual action schema preview only. It records user-reported broker actions and cannot verify or execute broker orders.",
        }

    def _paper_option_ledger_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "PAPER_LEDGER_READY",
            "schema_version": "paper_option_ledger_v1",
            "entry": {
                "status": "PAPER_OPTION_ENTRY_OPEN",
                "entry_event_id": 123,
                "ticker": "EXAMPLE",
                "direction": "put",
                "contract_symbol": "EXAMPLE260612P00100000",
                "entry_price": 0.42,
                "quantity": 1,
                "entry_debit_dollars": 42.0,
                "paper_only": True,
            },
            "close": {
                "status": "PAPER_OPTION_CLOSED",
                "entry_event_id": 123,
                "exit_price": 0.55,
                "pnl_dollars": 13.0,
                "return_pct": 0.30952,
                "learning_classification": {"classification": "GOOD_SIGNAL"},
            },
            "summary": {
                "open_count": 0,
                "closed_count": 1,
                "win_rate": 1.0,
                "total_pnl_dollars": 13.0,
            },
            "notes": "Static paper-ledger schema preview only. It logs manual/paper ideas and outcomes, never broker orders.",
        }

    def _journal_checkpoint_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "JOURNAL_CHECKPOINT_READY",
            "schema_version": "journal_checkpoint_v1",
            "event_count": 3,
            "latest_event_id": 123,
            "event_type_counts": {
                "live_review_cycle": 1,
                "manual_option_paper_close": 1,
                "learning_outcome_classification": 1,
            },
            "events": [
                {
                    "id": 123,
                    "timestamp": "2026-06-10T13:30:00Z",
                    "event_type": "live_review_cycle",
                    "payload": {"status": "NO_TRADE_PLAN"},
                }
            ],
            "notes": "Static checkpoint schema preview only. The live tool exports local journal evidence and cannot execute broker actions.",
        }

    def _journal_checkpoint_restore_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "CHECKPOINT_RESTORE_READY",
            "schema_version": "journal_checkpoint_restore_v1",
            "source_label": "saved_checkpoint",
            "requested_event_count": 3,
            "restored_count": 3,
            "skipped_duplicate_count": 0,
            "invalid_count": 0,
            "restored_event_type_counts": {
                "live_review_cycle": 1,
                "manual_option_paper_close": 1,
                "learning_outcome_classification": 1,
            },
            "restored_events": [
                {"id": 201, "event_type": "live_review_cycle", "original_id": 123}
            ],
            "notes": "Static restore preview only. The live tool restores local MCP journal evidence and cannot execute broker actions.",
        }

    def _session_risk_guard_schema_preview(self) -> dict[str, Any]:
        return {
            "status": "SESSION_RISK_CLEAR",
            "schema_version": "session_risk_guard_v1",
            "account_value_reference": 50.0,
            "proposed_risk_dollars": 5.0,
            "per_trade_cap_dollars": 5.0,
            "total_open_risk_cap_dollars": 15.0,
            "open_position_count": 0,
            "open_risk_dollars": 0.0,
            "projected_open_risk_dollars": 5.0,
            "closed_pnl_dollars": 0.0,
            "closed_trade_count": 0,
            "trading_day": "2026-06-11",
            "trading_day_timezone": "America/Chicago",
            "paper_open_position_count": 0,
            "real_cash_open_position_count": 0,
            "daily_closed_pnl_dollars": 0.0,
            "daily_closed_trade_count": 0,
            "daily_loss_count": 0,
            "daily_win_count": 0,
            "daily_flat_count": 0,
            "daily_loss_lockout_count": None,
            "daily_loss_lockout_triggered": False,
            "paper_daily_closed_pnl_dollars": 0.0,
            "paper_daily_closed_trade_count": 0,
            "paper_daily_loss_count": 0,
            "paper_daily_win_count": 0,
            "paper_daily_flat_count": 0,
            "real_cash_daily_closed_pnl_dollars": 0.0,
            "real_cash_daily_closed_trade_count": 0,
            "real_cash_daily_loss_count": 0,
            "real_cash_daily_win_count": 0,
            "real_cash_daily_flat_count": 0,
            "real_cash_daily_loss_lockout_count": 3,
            "real_cash_daily_loss_lockout_triggered": False,
            "next_action": "Risk journal is clear for review; still require live review cycle and manual trade desk.",
            "rules": [
                "Journal evidence only; broker balances are not verified.",
                "Paper/research scanning, paper entries, and paper closes are uncapped for learning.",
                "Block real-cash/autonomous escalation after 3 user-reported real-cash closed losses in the current trading day.",
                "No market orders.",
                "No broker action from this MCP.",
            ],
            "notes": "Static session-risk preview only. The live route summarizes local journal risk and cannot execute broker actions.",
        }

    def _required_tool_status(self, tools: list[str]) -> dict[str, bool]:
        required = [
            "get_version",
            "run_scalp_scan",
            "get_event_volatility_playbook",
            "get_event_radar",
            "run_event_volatility_scan",
            "run_broad_opportunity_scan",
            "get_data_truth_cockpit",
            "get_system_communication_audit",
            "get_strategy_module_registry",
            "get_shared_intelligence_layer",
            "get_autonomous_launch_decision",
            "get_real_cash_proof_gate",
            "get_broker_proof_bridge",
            "market_readiness_check",
            "run_review_harvest",
            "get_market_session_playbook",
            "run_latest_harvest_followup",
            "get_ops_command_center",
            "get_trading_day_launch_checklist",
            "get_tomorrow_operator_brief",
            "run_go_live_rehearsal",
            "run_trading_day_heartbeat",
            "summarize_trading_day_alerts",
            "run_morning_readiness_autopilot",
            "run_autonomous_morning_scan",
            "run_live_review_cycle",
            "run_market_open_observer",
            "run_observer_followup",
            "build_manual_trade_preflight_ticket",
            "build_manual_trade_desk",
            "log_manual_broker_action",
            "log_manual_option_paper_entry",
            "close_manual_option_paper_trade",
            "watch_manual_option_position",
            "summarize_manual_option_paper_trades",
            "get_session_risk_guard",
            "get_failure_mode_audit",
            "get_options_data_status",
            "get_truth_source_status",
            "check_market_data_health",
            "get_catalyst_context",
            "export_journal_checkpoint",
            "restore_journal_checkpoint",
            "get_trading_monster_blueprint",
            "get_feature_registry",
            "get_scoring_model",
            "explain_premove_score",
            "build_evidence_packet",
            "build_evidence_packets_from_scan",
            "summarize_evidence_packets",
            "build_setup_fingerprint",
            "compare_setup_memory",
            "set_autonomous_trading_controls",
            "get_trading_monster_dashboard",
            "get_cross_asset_capital_plan",
            "get_full_market_visibility_map",
            "get_listed_equity_master_universe",
            "get_event_volatility_war_room",
            "get_loss_review_reassessment",
            "get_broker_executor_bridge",
            "get_robinhood_crypto_universe",
            "get_crypto_live_test_gate",
            "run_autonomous_crypto_cycle",
            "summarize_crypto_live_test_report",
        ]
        available = set(tools)
        return {name: name in available for name in required}

    def _category(self, name: str) -> str:
        if "crypto" in name:
            return "crypto_validation"
        if "truth" in name or "health" in name or "catalyst" in name:
            return "truth_validation"
        if "harvest" in name or "readiness" in name or "observer" in name or "playbook" in name or "command_center" in name or "launch" in name or "brief" in name or "rehearsal" in name or "heartbeat" in name or "autopilot" in name or "autonomous" in name or "cycle" in name or "preflight" in name or "desk" in name or "manual_broker" in name or "paper" in name or "journal" in name or "checkpoint" in name:
            return "market_operations"
        if "evidence" in name or "blueprint" in name or "feature" in name or "scoring" in name:
            return "research_validation"
        if "scan" in name or "ticker" in name:
            return "market_review"
        if "option" in name:
            return "options_review"
        if "risk" in name or "safety" in name or "status" in name or "failure_mode" in name:
            return "safety"
        if "learning" in name or "outcome" in name or "postmortem" in name:
            return "learning"
        return "general"

    def _tool_notes(self, name: str) -> str:
        if name.startswith("generate_trade_plan"):
            return "Review-only plan generator; cannot place broker orders."
        if "evidence" in name:
            return "Research/audit packet tool for replay and learning."
        if "harvest" in name:
            return "Review-only scan, options review, ranking, and follow-up planning."
        if "readiness" in name:
            return "Review-only market readiness check; no trade plan or broker action."
        if "playbook" in name:
            return "Review-only market session operating checklist."
        if "command_center" in name:
            return "Review-only command center summary; reads logs and suggests the next safe action."
        if "launch" in name:
            return "Review-only trading-day launch checklist; maps go/no-go gates and next safe actions."
        if "brief" in name:
            return "Review-only tomorrow operator brief; maps safe pages, fallback validation, and hard stops."
        if "rehearsal" in name:
            return "Review-only go-live rehearsal; checks workflow readiness and required URLs without broker action."
        if "autopilot" in name:
            return "Review-only morning readiness summary; checks data readiness, ledger state, and next safe action."
        if "autonomous" in name:
            return "Review-only phase-aware scan loop; observes, logs, and returns the next refresh interval without broker action."
        if "crypto" in name:
            return "Crypto validation/scanning/reporting tool; cannot place exchange orders."
        if "cycle" in name:
            return "Review-only live market cycle; runs readiness and harvest gates without broker action."
        if "followup" in name and "observer" in name:
            return "Review-only observer follow-up; grades skipped/pass rows for missed-move learning without broker action."
        if "observer" in name:
            return "Review-only market-open observer; records scan evidence and deltas without options review or broker action."
        if "preflight" in name:
            return "Review-only broker snapshot, risk, and manual ticket preflight."
        if "desk" in name:
            return "Review-only manual trade desk that combines preflight, paper logging payload, and checkpoint reminder."
        if "manual_broker" in name:
            return "Review-only journal for user-reported broker actions; prepares pending-buy recheck cards without broker access."
        if "paper" in name:
            return "Paper/manual ledger for tracking hypothetical option entries and exits; no broker contact."
        if "journal" in name or "checkpoint" in name:
            return "Read-only journal checkpoint/export for preserving local review and learning evidence."
        if "failure_mode" in name:
            return "Read-only control audit mapping known trading-bot failure modes to current safeguards and gaps."
        if "truth" in name:
            return "Read-only source readiness summary for market data, options truth, and cash-readiness blockers."
        if "health" in name:
            return "Read-only data freshness check for quote and candle health."
        if "catalyst" in name:
            return "Read-only catalyst/news/earnings guard; missing or risky context fails closed."
        if "scan" in name:
            return "Review-only scan; no execution path."
        return "Review-only tool."

    def _safety(self) -> dict[str, bool]:
        return {
            "review_only": True,
            "can_place_order_from_this_mcp": False,
            "can_cancel_order_from_this_mcp": False,
            "market_orders_allowed": False,
            "debug_routes_do_not_run_scans": True,
        }
