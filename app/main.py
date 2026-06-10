from __future__ import annotations

from app.auth import BearerAuthMiddleware
from app.config import get_settings
from app.fallback_endpoints import (
    fallback_check_review_outcome,
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
    fallback_learning_classify,
    fallback_learning_dashboard,
    fallback_learning_proposals,
    fallback_log_review_decision,
    fallback_market_scan,
    fallback_health_full,
    fallback_offhours_plan,
    fallback_options_review,
    fallback_premove_blueprint,
    fallback_safety,
    fallback_scalp_scan,
    fallback_scoring_model,
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
    app.add_route("/review/options", fallback_options_review, methods=["GET"])
    app.add_route("/review/broker-option-snapshot", fallback_validate_broker_snapshot, methods=["POST"])
    app.add_route("/review/log-decision", fallback_log_review_decision, methods=["POST"])
    app.add_route("/review/outcome", fallback_check_review_outcome, methods=["GET", "POST"])
    app.add_route("/learning/classify", fallback_learning_classify, methods=["POST"])
    app.add_route("/learning/proposals", fallback_learning_proposals, methods=["POST"])
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
