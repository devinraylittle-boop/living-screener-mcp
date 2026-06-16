from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.stock_bridge_loop import parse_args

GATES_PATH = ROOT / "config" / "autonomous_readiness_gates.json"
PACKAGE_PATH = ROOT / "dist" / "living-screener-autonomous-trading-optimized-20260616.zip"


def _check_parse_inside_caps() -> tuple[bool, str | None]:
    env = {
        "AUTONOMY_STAGE": "stage_3_human_approved_live_trades",
        "STOCK_BRIDGE_LIVE_AUTH": "ENABLE_AGENTIC_STOCK_BRIDGE",
        "STOCK_BRIDGE_MAX_ORDER_NOTIONAL": "10",
        "STOCK_BRIDGE_MAX_DAILY_LOSS": "5",
        "STOCK_BRIDGE_BROKER": "robinhood",
    }
    try:
        with patch.dict(os.environ, env, clear=False):
            parse_args(["--broker", "robinhood", "--live", "--once"])
    except SystemExit as exc:
        return False, str(exc)
    return True, None


def _check_parse_cap_refusal() -> tuple[bool, str | None]:
    env = {
        "AUTONOMY_STAGE": "stage_3_human_approved_live_trades",
        "STOCK_BRIDGE_LIVE_AUTH": "ENABLE_AGENTIC_STOCK_BRIDGE",
    }
    try:
        with patch.dict(os.environ, env, clear=False):
            parse_args(["--broker", "robinhood", "--live", "--once", "--max-order-notional", "25", "--max-daily-loss", "5"])
    except SystemExit as exc:
        return "max_order_notional" in str(exc), str(exc)
    return False, "Cap violation was not refused."


def build_report() -> dict[str, Any]:
    gates = json.loads(GATES_PATH.read_text(encoding="utf-8"))
    stage3 = (gates.get("stage_limits") or {}).get("stage_3_human_approved_live_trades") or {}
    required_files = [
        "tools/start_stock_bridge_loop.ps1",
        "tools/stop_stock_bridge.ps1",
        "tools/status_stock_bridge.ps1",
        "tools/stock_bridge_loop.py",
        "tools/stage3_readiness_report.py",
        "config/autonomous_readiness_gates.json",
        "docs/TOMORROW_REMOTE_CONTROL_RUNBOOK.md",
    ]
    missing_files = [item for item in required_files if not (ROOT / item).exists()]
    parse_ok, parse_error = _check_parse_inside_caps()
    cap_refusal_ok, cap_refusal_note = _check_parse_cap_refusal()
    checks = {
        "global_live_default_false": gates.get("global_live_default") is False,
        "stage3_live_orders_true": stage3.get("live_orders") is True,
        "stage3_human_required": stage3.get("human_required") is True,
        "stage3_max_order_notional_10": float(stage3.get("max_order_notional_usd") or 0) == 10.0,
        "stage3_max_daily_loss_5": float(stage3.get("max_daily_loss_usd") or 0) == 5.0,
        "stage3_parser_accepts_inside_caps": parse_ok,
        "stage3_parser_refuses_cap_violation": cap_refusal_ok,
        "stage4_requires_all_gates": ((gates.get("stage_limits") or {}).get("stage_4_limited_autonomous_live_trades") or {}).get("requires_all_gates") is True,
        "stage5_requires_external_monitoring": ((gates.get("stage_limits") or {}).get("stage_5_full_autonomous_with_strict_caps") or {}).get("requires_external_monitoring") is True,
        "required_stage3_files_present": not missing_files,
        "package_built": PACKAGE_PATH.exists(),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    operator_auth_present = os.getenv("STOCK_BRIDGE_LIVE_AUTH") == "ENABLE_AGENTIC_STOCK_BRIDGE"
    return {
        "status": "STAGE3_CODE_READY" if not blockers else "STAGE3_BLOCKED",
        "runtime_authorized": operator_auth_present,
        "runtime_status": "READY_TO_RUN_WITH_OPERATOR_APPROVAL" if not blockers and operator_auth_present else "CODE_READY_OPERATOR_AUTH_REQUIRED" if not blockers else "BLOCKED",
        "checks": checks,
        "blockers": blockers,
        "missing_files": missing_files,
        "parse_error": parse_error,
        "cap_refusal_note": cap_refusal_note,
        "stage3_scope": "Small, human-approved Robinhood equity orders only. Alpaca remains paper-only in this package.",
        "stage3_limits": {
            "max_order_notional_usd": stage3.get("max_order_notional_usd"),
            "max_daily_loss_usd": stage3.get("max_daily_loss_usd"),
            "human_required": stage3.get("human_required"),
        },
        "stage4_5_autonomy": "blocked_until_readiness_gates_pass",
        "can_place_order_from_this_report": False,
    }


def main() -> int:
    print(json.dumps(build_report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
