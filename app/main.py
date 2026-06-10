from __future__ import annotations

from app.auth import BearerAuthMiddleware
from app.config import get_settings
from app.fallback_endpoints import (
    fallback_check_review_outcome,
    fallback_command_center,
    fallback_crypto_backtest,
    fallback_crypto_rules,
    fallback_build_evidence_packet,
    fallback_build_evidence_packets_from_scan,
    fallback_debug_scan_schema,
    fallback_debug_tool_manifest,
    fallback_evidence_summary,
    fallback_explain_premove_score,
    fallback_feature_registry,
    fallback_global_research_scan,
    fallback_harvest_followup,
    fallback_journal_checkpoint,
    fallback_learning_classify,
    fallback_learning_dashboard,
    fallback_learning_proposals,
    fallback_setup_memory,
    fallback_live_review_cycle,
    fallback_log_review_decision,
    fallback_manual_preflight,
    fallback_manual_broker_action,
    fallback_manual_trade_desk,
    fallback_market_open_observer,
    fallback_market_scan,
    fallback_market_readiness,
    fallback_health_full,
    fallback_morning_autopilot,
    fallback_observer_followup,
    fallback_offhours_plan,
    fallback_options_review,
    fallback_paper_option_close,
    fallback_paper_option_entry,
    fallback_paper_option_summary,
    fallback_pending_recheck,
    fallback_review_harvest,
    fallback_premove_blueprint,
    fallback_session_playbook,
    fallback_safety,
    fallback_scalp_scan,
    fallback_scoring_model,
    fallback_trading_day_launch,
    fallback_trading_day_heartbeat,
    fallback_validate_broker_snapshot,
)
from app.health import health, safe_config, tools, version
from app.logging_config import configure_logging
from app.mcp_server import mcp


def create_app():
    configure_logging()
    settings = get_settings()
    app = mcp.http_app(path="/mcp", transport="streamable-http")
    app.state.settings = settings
    app.state.mcp = mcp
    app.add_route("/health", health, methods=["GET"])
    app.add_route("/health/full", fallback_health_full, methods=["GET"])
    app.add_route("/config", safe_config, methods=["GET"])
    app.add_route("/version", version, methods=["GET"])
    app.add_route("/tools", tools, methods=["GET"])
    app.add_route("/safety", fallback_safety, methods=["GET"])
    app.add_route("/scan/market", fallback_market_scan, methods=["GET"])
    app.add_route("/scan/scalp", fallback_scalp_scan, methods=["GET"])
    app.add_route("/ops/market-readiness", fallback_market_readiness, methods=["GET"])
    app.add_route("/ops/review-harvest", fallback_review_harvest, methods=["GET"])
    app.add_route("/ops/session-playbook", fallback_session_playbook, methods=["GET"])
    app.add_route("/ops/harvest-followup", fallback_harvest_followup, methods=["GET"])
    app.add_route("/ops/command-center", fallback_command_center, methods=["GET"])
    app.add_route("/ops/trading-day-launch", fallback_trading_day_launch, methods=["GET"])
    app.add_route("/ops/day-heartbeat", fallback_trading_day_heartbeat, methods=["GET"])
    app.add_route("/ops/morning-autopilot", fallback_morning_autopilot, methods=["GET"])
    app.add_route("/ops/live-review-cycle", fallback_live_review_cycle, methods=["GET"])
    app.add_route("/ops/market-open-observer", fallback_market_open_observer, methods=["GET"])
    app.add_route("/ops/observer-followup", fallback_observer_followup, methods=["GET"])
    app.add_route("/review/options", fallback_options_review, methods=["GET"])
    app.add_route("/review/manual-preflight", fallback_manual_preflight, methods=["GET", "POST"])
    app.add_route("/trade/manual-desk", fallback_manual_trade_desk, methods=["GET", "POST"])
    app.add_route("/trade/manual-action", fallback_manual_broker_action, methods=["GET", "POST"])
    app.add_route("/trade/pending-recheck", fallback_pending_recheck, methods=["GET", "POST"])
    app.add_route("/review/broker-option-snapshot", fallback_validate_broker_snapshot, methods=["POST"])
    app.add_route("/paper/options/entry", fallback_paper_option_entry, methods=["POST"])
    app.add_route("/paper/options/close", fallback_paper_option_close, methods=["POST"])
    app.add_route("/paper/options/summary", fallback_paper_option_summary, methods=["GET"])
    app.add_route("/journal/checkpoint", fallback_journal_checkpoint, methods=["GET", "POST"])
    app.add_route("/review/log-decision", fallback_log_review_decision, methods=["POST"])
    app.add_route("/review/outcome", fallback_check_review_outcome, methods=["GET", "POST"])
    app.add_route("/learning/classify", fallback_learning_classify, methods=["POST"])
    app.add_route("/learning/proposals", fallback_learning_proposals, methods=["POST"])
    app.add_route("/learning/setup-memory", fallback_setup_memory, methods=["POST"])
    app.add_route("/learning/dashboard", fallback_learning_dashboard, methods=["GET"])
    app.add_route("/research/offhours", fallback_offhours_plan, methods=["GET"])
    app.add_route("/research/global-scan", fallback_global_research_scan, methods=["GET"])
    app.add_route("/research/blueprint", fallback_premove_blueprint, methods=["GET"])
    app.add_route("/research/features", fallback_feature_registry, methods=["GET"])
    app.add_route("/research/scoring-model", fallback_scoring_model, methods=["GET"])
    app.add_route("/research/explain-score", fallback_explain_premove_score, methods=["POST"])
    app.add_route("/research/evidence-packet", fallback_build_evidence_packet, methods=["POST"])
    app.add_route("/research/evidence-packets-from-scan", fallback_build_evidence_packets_from_scan, methods=["POST"])
    app.add_route("/research/evidence-summary", fallback_evidence_summary, methods=["GET", "POST"])
    app.add_route("/debug/tool-manifest", fallback_debug_tool_manifest, methods=["GET"])
    app.add_route("/debug/scan-schema", fallback_debug_scan_schema, methods=["GET"])
    app.add_route("/crypto/rules", fallback_crypto_rules, methods=["GET"])
    app.add_route("/crypto/backtest", fallback_crypto_backtest, methods=["GET"])
    app.add_middleware(BearerAuthMiddleware, settings=settings)
    return app


app = create_app()
