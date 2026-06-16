from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from tools.execution_order_validator import validate_execution_order_file
from tools.stage4_readiness_report import build_report as build_stage4_report
from tools.stock_bridge_loop import parse_args

GATES_PATH = ROOT / "config" / "autonomous_readiness_gates.json"
PACKAGE_PATH = ROOT / "dist" / "living-screener-autonomous-trading-optimized-20260616.zip"


def _bool_env(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _check_stage5_parser_refusal() -> tuple[bool, str | None]:
    env = {
        "AUTONOMY_STAGE": "stage_5_full_autonomous_with_strict_caps",
        "STOCK_BRIDGE_LIVE_AUTH": "ENABLE_AGENTIC_STOCK_BRIDGE",
        "STOCK_BRIDGE_BROKER": "robinhood",
    }
    try:
        with patch.dict(os.environ, env, clear=False):
            parse_args(["--broker", "robinhood", "--live", "--once", "--max-order-notional", "1"])
    except SystemExit as exc:
        text = str(exc)
        return "Full or limited autonomous live trading remains blocked" in text or "requested stage_5" in text, text
    return False, "Stage 5 live startup was not refused."


def _process_ids(commandline_contains: list[str]) -> list[int]:
    if os.name != "nt":
        return []
    query = (
        "Get-CimInstance Win32_Process | Where-Object { "
        + "$_.Name -eq 'python.exe' -and "
        + " -and ".join([f"$_.CommandLine -like '*{item}*'" for item in commandline_contains])
        + " } | Select-Object -ExpandProperty ProcessId"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", query],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    ids: list[int] = []
    for line in result.stdout.splitlines():
        try:
            ids.append(int(line.strip()))
        except ValueError:
            continue
    return ids


def _state_summary() -> dict[str, Any]:
    path = ROOT / "data" / "stock_bridge_state.json"
    if not path.exists():
        return {"present": False}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"present": True, "readable": False, "error": repr(exc)}
    return {
        "present": True,
        "readable": True,
        "broker": state.get("broker"),
        "scope": state.get("scope"),
        "trade_count": state.get("trade_count"),
        "halted": state.get("halted"),
        "pause_reason": state.get("pause_reason"),
        "new_entries_paused_until": state.get("new_entries_paused_until"),
    }


def _local_health() -> dict[str, Any]:
    settings = get_settings()
    alpaca_base_url = os.getenv("ALPACA_BASE_URL", "")
    paper_processes = _process_ids(["stock_bridge_loop.py", "--broker alpaca"])
    robinhood_live_processes = _process_ids(["stock_bridge_loop.py", "--broker robinhood", "--live"])
    return {
        "package_built": PACKAGE_PATH.exists(),
        "app_review_only": settings.review_only,
        "app_place_orders": settings.place_orders,
        "app_market_orders_allowed": settings.market_orders_allowed,
        "app_manual_approval_required": settings.manual_approval_required,
        "market_data_provider": settings.market_data_provider,
        "options_data_provider": settings.options_data_provider,
        "has_finnhub_key": bool(settings.finnhub_api_key),
        "has_tradier_token": bool(settings.tradier_access_token),
        "alpaca_base_url_is_paper": "paper-api.alpaca.markets" in alpaca_base_url.lower(),
        "alpaca_credentials_present": bool(os.getenv("ALPACA_API_KEY_ID")) and bool(os.getenv("ALPACA_API_SECRET_KEY")),
        "alpaca_paper_process_running": bool(paper_processes),
        "alpaca_paper_process_ids": paper_processes,
        "robinhood_live_process_running": bool(robinhood_live_processes),
        "robinhood_live_process_ids": robinhood_live_processes,
        "bridge_state": _state_summary(),
    }


def build_report() -> dict[str, Any]:
    gates = json.loads(GATES_PATH.read_text(encoding="utf-8"))
    stage5 = (gates.get("stage_limits") or {}).get("stage_5_full_autonomous_with_strict_caps") or {}
    stage4 = build_stage4_report()
    execution_order = validate_execution_order_file()
    local = _local_health()
    stage5_refused, stage5_refusal_note = _check_stage5_parser_refusal()

    critical_checks = {
        "stage5_startup_refused_until_all_gates_pass": stage5_refused,
        "stage5_requires_90_day_clean_record": stage5.get("requires_90_day_clean_record") is True,
        "stage5_requires_external_monitoring": stage5.get("requires_external_monitoring") is True,
        "stage5_requires_monthly_model_review": stage5.get("requires_monthly_model_review") is True,
        "execution_order_validated": execution_order.get("status") == "EXECUTION_ORDER_VALIDATED",
        "stage4_not_ready_for_live_autonomy": stage4.get("runtime_status") != "READY_TO_ENABLE_LIMITED_AUTONOMOUS_LIVE",
        "app_layer_fail_closed": local["app_review_only"] is True and local["app_place_orders"] is False and local["app_market_orders_allowed"] is False,
        "alpaca_paper_configured": local["alpaca_base_url_is_paper"] is True and local["alpaca_credentials_present"] is True,
        "alpaca_paper_running": local["alpaca_paper_process_running"] is True,
        "robinhood_live_bridge_not_running": local["robinhood_live_process_running"] is False,
        "package_built": local["package_built"] is True,
    }
    critical_failures = [name for name, passed in critical_checks.items() if not passed]

    runtime_blockers = list(stage4.get("runtime_blockers") or [])
    runtime_blockers.extend(
        [
            "stage5_90_day_clean_record_not_available",
            "external_monitoring_not_connected",
            "monthly_model_review_not_established",
            "options_realtime_broker_truth_not_connected",
            "live_crypto_not_connected",
            "operator_absent_tomorrow_requires_no_live_cash_autonomy",
        ]
    )
    if execution_order.get("status") != "EXECUTION_ORDER_VALIDATED":
        runtime_blockers.append("execution_order_has_unresolved_authority_or_risk_fields")

    known_weaknesses = [
        "paper sample is too small for live promotion",
        "only one market day of closed paper evidence",
        "external alerting/monitoring is not connected",
        "secrets rotation is not confirmed",
        "broker reconciliation snapshot is not continuously automated",
        "options realtime truth remains broker/manual or unconnected",
        "no autonomous live crypto connector is active",
        "L2/order-flow, catalyst context, and sector-relative strength are still missing or diagnostic only",
    ]
    if execution_order.get("status") != "EXECUTION_ORDER_VALIDATED":
        known_weaknesses.append("full-autonomy execution order still contains unresolved bracketed authority/risk fields")

    final_decision = "NO_GO_LIVE_AUTONOMY"
    enabled_mode = "STAGE_2_ALPACA_PAPER_ONLY"

    return {
        "status": "STAGE5_LOCKED_PAPER_ONLY" if not critical_failures else "STAGE5_HEALTH_BLOCKED",
        "final_decision": final_decision,
        "enabled_mode": enabled_mode,
        "review_only": True,
        "can_place_order_from_this_report": False,
        "critical_checks": critical_checks,
        "critical_failures": critical_failures,
        "runtime_blockers": runtime_blockers,
        "stage5_refusal_note": stage5_refusal_note,
        "execution_order_summary": {
            "status": execution_order.get("status"),
            "decision": execution_order.get("decision"),
            "blockers": execution_order.get("blockers"),
            "unresolved_bracketed_fields": execution_order.get("unresolved_bracketed_fields"),
        },
        "broker_connection_status": {
            "alpaca_paper": "configured_and_running"
            if local["alpaca_base_url_is_paper"] and local["alpaca_credentials_present"] and local["alpaca_paper_process_running"]
            else "blocked_or_not_running",
            "alpaca_live": "disabled",
            "robinhood_read_only": "verified_externally_before_report",
            "robinhood_live_bridge": "not_running",
        },
        "account_permissions": {
            "robinhood_default_account": "cash; not agentic enabled; not eligible for autonomous tool orders",
            "robinhood_agentic_account": "cash; agentic enabled for equities; options level reported by broker but not enabled for autonomous package execution",
            "alpaca_paper": "ACTIVE paper account when credentials are loaded; stocks/options-contract probe/crypto-assets probe supported",
            "alpaca_live": "not configured or enabled",
        },
        "tradable_asset_classes_now": {
            "robinhood_equities_etfs": "read/review available; live autonomous disabled; Stage 3 human-approved only when operator is present",
            "robinhood_options": "portfolio/permission visibility only; autonomous options execution disabled",
            "robinhood_crypto": "not connected for autonomous package execution",
            "shorts_margin": "disabled for autonomous package; accounts are cash accounts",
            "alpaca_paper_stocks": "enabled",
            "alpaca_paper_options_contracts": "contract discovery validated; execution remains governed by paper bridge capability",
            "alpaca_paper_crypto": "asset universe validated; live crypto execution disabled",
        },
        "active_strategies": [
            "alpaca_paper_aggressive_stock_loop",
            "paper_lifecycle_ledger",
            "review_only_scalp_scan",
            "risk_and_journal_review",
        ],
        "disabled_strategies": [
            "stage5_live_cash_autonomy",
            "alpaca_live_cash_trading",
            "robinhood_unsupervised_live_equity_entries",
            "autonomous_options_cash_execution",
            "autonomous_crypto_cash_execution",
            "short_selling",
            "margin_trading",
            "market_orders_for_live_cash",
        ],
        "risk_limits_chosen": {
            "live_max_daily_loss_usd": 0.0,
            "live_max_position_size_usd": 0.0,
            "live_max_open_positions": 0,
            "live_allowed_order_types": [],
            "stage3_human_present_max_order_notional_usd": 10.0,
            "stage3_human_present_max_daily_loss_usd": 5.0,
            "paper_max_order_notional_usd": 250.0,
            "paper_max_open_positions": 10,
            "paper_max_trades_per_day": 50,
            "paper_stop_loss_pct": 0.01,
            "paper_take_profit_pct": 0.015,
        },
        "emergency_shutdown_conditions": [
            "any live bridge process appears without explicit Stage 3 operator presence",
            "paper bridge consecutive broker/data errors exceed configured threshold and enter cooldown",
            "daily loss cap reached",
            "duplicate open order detected for a symbol",
            "broker snapshot is missing or unreconciled",
            "market data becomes stale or inconsistent",
            "spread/liquidity gates fail",
            "unexpected account, endpoint, or secret-environment mismatch",
        ],
        "data_feed_status": {
            "scanner_provider": local["market_data_provider"],
            "scanner_provider_key_present": local["has_finnhub_key"],
            "options_provider": local["options_data_provider"],
            "tradier_token_present": local["has_tradier_token"],
            "alpaca_data_url": os.getenv("ALPACA_DATA_URL", ""),
        },
        "logging_status": {
            "paper_lifecycle_ledger": (ROOT / "data" / "paper_lifecycle_ledger.jsonl").exists(),
            "stock_bridge_log": (ROOT / "data" / "stock_bridge_loop.jsonl").exists(),
            "stock_bridge_state": local["bridge_state"],
            "decision_journal": "app event storage available through local database when running",
        },
        "known_weaknesses": known_weaknesses,
        "stage4_summary": {
            "status": stage4.get("status"),
            "runtime_status": stage4.get("runtime_status"),
            "paper_promotion_summary": stage4.get("paper_promotion_summary"),
            "broker_reconciliation_summary": stage4.get("broker_reconciliation_summary"),
        },
        "next_action": "Leave Alpaca paper running. Do not enable live cash autonomy tomorrow unless this report changes to GO and every runtime blocker is cleared.",
    }


def main() -> int:
    print(json.dumps(build_report(), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
