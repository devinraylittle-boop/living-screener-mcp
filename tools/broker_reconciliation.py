from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "stock_bridge_state.json"
GATES_PATH = ROOT / "config" / "autonomous_readiness_gates.json"

ACTIVE_ORDER_STATES = {
    "accepted",
    "confirmed",
    "held",
    "new",
    "open",
    "partially_filled",
    "pending",
    "pending_cancel",
    "queued",
    "submitted",
    "unconfirmed",
}


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_json(path: Path) -> tuple[dict[str, Any], bool, str | None]:
    if not path.exists():
        return {}, True, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, False, repr(exc)
    return data if isinstance(data, dict) else {}, True, None


def normalize_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        rows = value.get("items") or value.get("results") or value.get("orders") or value.get("positions")
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    return []


def row_symbol(row: dict[str, Any]) -> str:
    return str(row.get("symbol") or row.get("ticker") or row.get("asset_symbol") or "").upper()


def row_state(row: dict[str, Any]) -> str:
    return str(row.get("state") or row.get("status") or row.get("order_status") or "").lower()


def row_quantity(row: dict[str, Any]) -> float:
    return as_float(row.get("quantity") or row.get("qty") or row.get("shares") or row.get("current_quantity"))


def active_open_orders(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = normalize_rows(snapshot.get("open_orders") or snapshot.get("orders"))
    active: list[dict[str, Any]] = []
    for row in rows:
        state = row_state(row)
        if not state or state in ACTIVE_ORDER_STATES:
            active.append(row)
    return active


def active_positions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in normalize_rows(snapshot.get("positions")) if row_quantity(row) > 0]


def duplicate_order_symbols(open_orders: list[dict[str, Any]]) -> list[str]:
    counts = Counter(row_symbol(row) for row in open_orders if row_symbol(row))
    return sorted(symbol for symbol, count in counts.items() if count > 1)


def build_reconciliation_report(
    *,
    snapshot: dict[str, Any] | None = None,
    snapshot_path: Path | None = None,
    state_path: Path = STATE_PATH,
    gates_path: Path = GATES_PATH,
    root: Path = ROOT,
) -> dict[str, Any]:
    supplied_snapshot = snapshot is not None or snapshot_path is not None
    snapshot_error: str | None = None
    if snapshot is None and snapshot_path is not None:
        snapshot, ok, snapshot_error = load_json(snapshot_path)
        supplied_snapshot = ok
    snapshot = snapshot or {}

    state, state_readable, state_error = load_json(state_path)
    gates, gates_readable, gates_error = load_json(gates_path)
    required = gates.get("required_before_limited_autonomous_live") or {}
    max_open_positions = int(required.get("max_open_positions") or 2)

    open_orders = active_open_orders(snapshot)
    positions = active_positions(snapshot)
    duplicates = duplicate_order_symbols(open_orders)
    symbols_with_orders = sorted({row_symbol(row) for row in open_orders if row_symbol(row)})
    symbols_with_positions = sorted({row_symbol(row) for row in positions if row_symbol(row)})
    missing_order_symbols = [idx for idx, row in enumerate(open_orders) if not row_symbol(row)]

    checks = {
        "broker_snapshot_supplied": supplied_snapshot,
        "gates_readable": gates_readable,
        "local_state_readable_or_absent": state_readable,
        "open_orders_have_symbols": not missing_order_symbols,
        "no_duplicate_open_orders": not duplicates,
        "open_positions_within_gate": len(positions) <= max_open_positions,
        "kill_switch_present": (root / "tools" / "stop_stock_bridge.ps1").exists(),
        "paper_kill_switch_present": (root / "tools" / "stop_alpaca_paper.ps1").exists(),
        "status_scripts_present": (root / "tools" / "status_stock_bridge.ps1").exists()
        and (root / "tools" / "status_paper_lifecycle.ps1").exists(),
    }
    blockers = [name for name, passed in checks.items() if not passed]

    return {
        "status": "BROKER_RECONCILIATION_READY" if not blockers else "BROKER_RECONCILIATION_BLOCKED",
        "review_only": True,
        "can_place_order_from_this_report": False,
        "broker": str(snapshot.get("broker") or state.get("broker") or "unknown"),
        "scope": str(snapshot.get("scope") or state.get("scope") or "unknown"),
        "snapshot_source": str(snapshot_path) if snapshot_path else "provided_snapshot" if supplied_snapshot else "none",
        "checks": checks,
        "blockers": blockers,
        "open_order_count": len(open_orders),
        "open_position_count": len(positions),
        "max_open_positions_gate": max_open_positions,
        "symbols_with_open_orders": symbols_with_orders,
        "symbols_with_positions": symbols_with_positions,
        "duplicate_open_order_symbols": duplicates,
        "missing_order_symbol_indexes": missing_order_symbols,
        "state_summary": {
            "present": state_path.exists(),
            "trade_count": state.get("trade_count"),
            "halted": state.get("halted"),
            "pause_reason": state.get("pause_reason"),
            "new_entries_paused_until": state.get("new_entries_paused_until"),
        },
        "errors": {
            "snapshot": snapshot_error,
            "state": state_error,
            "gates": gates_error,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only broker reconciliation report.")
    parser.add_argument("--snapshot", type=Path, help="Optional JSON snapshot with positions and open_orders.")
    args = parser.parse_args(argv)
    report = build_reconciliation_report(snapshot_path=args.snapshot)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
