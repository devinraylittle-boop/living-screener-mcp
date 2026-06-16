from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORDER_PATH = ROOT / "config" / "full_autonomy_execution_order.txt"
DEFAULT_LIVE_CASH_ORDER_PATH = ROOT / "config" / "live_cash_authority_order.txt"

BRACKETED_FIELD_RE = re.compile(r"\[[^\]]+\]")
FINAL_COMMANDS = (
    "Begin autonomous monitoring and trading only after all bracketed fields above are completed and validated.",
    "Begin limited live-cash autonomous monitoring and trading only after this live-cash authority package validates and every Stage 5 live-cash promotion gate passes.",
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def bracketed_fields(text: str) -> list[str]:
    return sorted(set(BRACKETED_FIELD_RE.findall(text)))


def validate_execution_order_text(text: str, *, source: str = "inline") -> dict[str, Any]:
    fields = bracketed_fields(text)
    has_final_command = any(command in text for command in FINAL_COMMANDS)
    required_sections = [
        "ACCOUNT AND MARKET AUTHORITY",
        "PRIMARY OBJECTIVE",
        "NON-NEGOTIABLE RISK LIMITS",
        "MANDATORY PRE-TRADE CHECK",
        "ORDER EXECUTION RULES",
        "POSITION MANAGEMENT",
        "KILL SWITCH CONDITIONS",
        "STRATEGY DISCIPLINE",
        "LOGGING AND REPORTING",
        "COMPLIANCE AND REFUSAL RULES",
        "FINAL OPERATING COMMAND",
    ]
    missing_sections = [section for section in required_sections if section not in text]
    checks = {
        "all_bracketed_fields_completed": not fields,
        "final_command_present": has_final_command,
        "required_sections_present": not missing_sections,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "status": "EXECUTION_ORDER_VALIDATED" if not blockers else "EXECUTION_ORDER_BLOCKED",
        "source": source,
        "review_only": True,
        "can_place_order_from_this_report": False,
        "checks": checks,
        "blockers": blockers,
        "unresolved_bracketed_fields": fields,
        "missing_sections": missing_sections,
        "decision": "NO_GO_LIVE_AUTONOMY" if blockers else "ORDER_TEXT_READY_FOR_STAGE_GATE_REVIEW",
        "next_action": (
            "Complete every bracketed authority/risk field, then re-run Stage 5 readiness. Live autonomy remains disabled until all Stage 5 gates pass."
            if blockers
            else "Execution order text is complete. Re-run Stage 5 readiness; live autonomy remains disabled until every runtime gate passes."
        ),
    }


def validate_execution_order_file(path: Path = DEFAULT_ORDER_PATH) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "EXECUTION_ORDER_BLOCKED",
            "source": str(path),
            "review_only": True,
            "can_place_order_from_this_report": False,
            "checks": {
                "execution_order_file_present": False,
                "all_bracketed_fields_completed": False,
                "required_sections_present": False,
            },
            "blockers": ["execution_order_file_present", "all_bracketed_fields_completed", "required_sections_present"],
            "unresolved_bracketed_fields": [],
            "missing_sections": [],
            "decision": "NO_GO_LIVE_AUTONOMY",
            "next_action": "Create a completed execution order before any Stage 5 live-autonomy review.",
        }
    return validate_execution_order_text(read_text(path), source=str(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the full-autonomy execution order.")
    parser.add_argument("--path", type=Path, default=DEFAULT_ORDER_PATH)
    args = parser.parse_args(argv)
    report = validate_execution_order_file(args.path)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
