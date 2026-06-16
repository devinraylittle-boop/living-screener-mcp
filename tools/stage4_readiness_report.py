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

from tools.broker_reconciliation import build_reconciliation_report
from tools.paper_lifecycle_ledger import summarize as summarize_paper_lifecycle
from tools.runtime_evidence import build_runtime_evidence_report
from tools.stock_bridge_loop import parse_args

GATES_PATH = ROOT / "config" / "autonomous_readiness_gates.json"
PACKAGE_PATH = ROOT / "dist" / "living-screener-autonomous-trading-optimized-20260616.zip"


def _check_stage4_parser_refusal() -> tuple[bool, str | None]:
    env = {
        "AUTONOMY_STAGE": "stage_4_limited_autonomous_live_trades",
        "STOCK_BRIDGE_LIVE_AUTH": "ENABLE_AGENTIC_STOCK_BRIDGE",
        "STOCK_BRIDGE_BROKER": "robinhood",
    }
    try:
        with patch.dict(os.environ, env, clear=False):
            parse_args(["--broker", "robinhood", "--live", "--once", "--max-order-notional", "25"])
    except SystemExit as exc:
        text = str(exc)
        return "Full or limited autonomous live trading remains blocked" in text or "requested stage_4" in text, text
    return False, "Stage 4 live startup was not refused."


def build_report() -> dict[str, Any]:
    gates = json.loads(GATES_PATH.read_text(encoding="utf-8"))
    required = gates.get("required_before_limited_autonomous_live") or {}
    stage4 = (gates.get("stage_limits") or {}).get("stage_4_limited_autonomous_live_trades") or {}
    paper = summarize_paper_lifecycle()
    snapshot_path_text = os.getenv("BROKER_RECONCILIATION_SNAPSHOT_PATH", "").strip()
    reconciliation = build_reconciliation_report(snapshot_path=Path(snapshot_path_text) if snapshot_path_text else None)
    runtime_evidence = build_runtime_evidence_report()
    stage4_refused, stage4_refusal_note = _check_stage4_parser_refusal()

    required_files = [
        "tools/broker_reconciliation.py",
        "tools/paper_lifecycle_ledger.py",
        "tools/runtime_evidence.py",
        "tools/stage4_readiness_report.py",
        "tools/status_stage4.ps1",
        "tools/status_runtime_evidence.ps1",
        "tools/status_paper_lifecycle.ps1",
        "tools/status_stock_bridge.ps1",
        "tools/stop_stock_bridge.ps1",
        "tools/stop_alpaca_paper.ps1",
        "config/autonomous_readiness_gates.json",
        "docs/TOMORROW_REMOTE_CONTROL_RUNBOOK.md",
    ]
    missing_files = [item for item in required_files if not (ROOT / item).exists()]

    code_checks = {
        "global_live_default_false": gates.get("global_live_default") is False,
        "stage4_requires_all_gates": stage4.get("requires_all_gates") is True,
        "stage4_live_startup_refused_until_gates_pass": stage4_refused,
        "stage4_files_present": not missing_files,
        "package_built": PACKAGE_PATH.exists(),
        "stage5_requires_external_monitoring": ((gates.get("stage_limits") or {}).get("stage_5_full_autonomous_with_strict_caps") or {}).get("requires_external_monitoring") is True,
    }
    runtime_checks = {
        "paper_promotion_ready": paper.get("status") == "PAPER_PROMOTION_READY",
        "broker_reconciliation_ready": reconciliation.get("status") == "BROKER_RECONCILIATION_READY",
        "duplicate_order_guard_ready": reconciliation.get("checks", {}).get("no_duplicate_open_orders") is True,
        "kill_switch_ready": reconciliation.get("checks", {}).get("kill_switch_present") is True
        and reconciliation.get("checks", {}).get("paper_kill_switch_present") is True,
        "operator_runbook_ready": (ROOT / "docs" / "TOMORROW_REMOTE_CONTROL_RUNBOOK.md").exists(),
        "external_alerting_ready": runtime_evidence.get("external_alerting_ready") is True,
        "secrets_rotation_confirmed": runtime_evidence.get("secrets_rotation_ready") is True,
    }

    code_blockers = [name for name, passed in code_checks.items() if not passed]
    runtime_blockers = [name for name, passed in runtime_checks.items() if not passed]
    status = "STAGE4_CODE_READY_RUNTIME_BLOCKED" if not code_blockers else "STAGE4_CODE_BLOCKED"
    if not code_blockers and not runtime_blockers:
        status = "STAGE4_READY_TO_ENABLE_LIMITED_AUTONOMOUS_LIVE"

    return {
        "status": status,
        "runtime_status": "READY_TO_ENABLE_LIMITED_AUTONOMOUS_LIVE" if not runtime_blockers and not code_blockers else "BLOCKED_UNTIL_READINESS_GATES_PASS",
        "review_only": True,
        "can_place_order_from_this_report": False,
        "code_checks": code_checks,
        "runtime_checks": runtime_checks,
        "code_blockers": code_blockers,
        "runtime_blockers": runtime_blockers,
        "missing_files": missing_files,
        "stage4_limits": {
            "max_order_notional_usd": stage4.get("max_order_notional_usd"),
            "max_daily_loss_pct_of_equity": stage4.get("max_daily_loss_pct_of_equity"),
            "requires_all_gates": stage4.get("requires_all_gates"),
            "human_required": stage4.get("human_required"),
        },
        "required_before_limited_autonomous_live": required,
        "paper_promotion_summary": {
            "status": paper.get("status"),
            "entry_count": paper.get("entry_count"),
            "promotion_eligible_closed_trade_count": paper.get("promotion_eligible_closed_trade_count"),
            "distinct_closed_trade_days": paper.get("distinct_closed_trade_days"),
            "profit_factor_after_costs": paper.get("profit_factor_after_costs"),
            "max_drawdown_pct": paper.get("max_drawdown_pct"),
            "blockers": paper.get("blockers"),
        },
        "runtime_evidence_summary": {
            "status": runtime_evidence.get("status"),
            "source": runtime_evidence.get("source"),
            "external_alerting_ready": runtime_evidence.get("external_alerting_ready"),
            "secrets_rotation_ready": runtime_evidence.get("secrets_rotation_ready"),
            "monthly_model_review_ready": runtime_evidence.get("monthly_model_review_ready"),
            "blockers": runtime_evidence.get("blockers"),
        },
        "broker_reconciliation_summary": {
            "status": reconciliation.get("status"),
            "snapshot_source": reconciliation.get("snapshot_source"),
            "open_order_count": reconciliation.get("open_order_count"),
            "open_position_count": reconciliation.get("open_position_count"),
            "duplicate_open_order_symbols": reconciliation.get("duplicate_open_order_symbols"),
            "blockers": reconciliation.get("blockers"),
        },
        "stage4_refusal_note": stage4_refusal_note,
        "next_action": "Keep aggressive paper trading running; Stage 4 live autonomy stays blocked until every runtime gate is green.",
    }


def main() -> int:
    print(json.dumps(build_report(), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
