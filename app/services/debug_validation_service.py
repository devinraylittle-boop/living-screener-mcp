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
            },
            "debug_routes": [
                "/health/full",
                "/debug/tool-manifest",
                "/debug/scan-schema",
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
            },
            "safety": self._safety(),
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
                "No OPRA-grade options chain in this build.",
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
            "setup_memory_schema_preview": self._setup_memory_schema_preview(),
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

    def _required_tool_status(self, tools: list[str]) -> dict[str, bool]:
        required = [
            "get_version",
            "run_scalp_scan",
            "get_trading_monster_blueprint",
            "get_feature_registry",
            "get_scoring_model",
            "explain_premove_score",
            "build_evidence_packet",
            "build_evidence_packets_from_scan",
            "summarize_evidence_packets",
            "build_setup_fingerprint",
            "compare_setup_memory",
        ]
        available = set(tools)
        return {name: name in available for name in required}

    def _category(self, name: str) -> str:
        if "evidence" in name or "blueprint" in name or "feature" in name or "scoring" in name:
            return "research_validation"
        if "scan" in name or "ticker" in name:
            return "market_review"
        if "option" in name:
            return "options_review"
        if "risk" in name or "safety" in name or "status" in name:
            return "safety"
        if "learning" in name or "outcome" in name or "postmortem" in name:
            return "learning"
        return "general"

    def _tool_notes(self, name: str) -> str:
        if name.startswith("generate_trade_plan"):
            return "Review-only plan generator; cannot place broker orders."
        if "evidence" in name:
            return "Research/audit packet tool for replay and learning."
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
