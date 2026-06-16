from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "data" / "paper_lifecycle_ledger.jsonl"
READINESS_GATES_PATH = ROOT / "config" / "autonomous_readiness_gates.json"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def append_ledger_event(event: dict[str, Any], path: Path = LEDGER_PATH) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "paper_lifecycle_ledger_v1",
        "timestamp": utc_now(),
        **event,
    }
    path.open("a", encoding="utf-8").write(json.dumps(payload, sort_keys=True, default=str) + "\n")
    return payload


def read_ledger(path: Path = LEDGER_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def record_entry(
    *,
    broker: str,
    scope: str,
    symbol: str,
    order_id: str | None,
    order_status: str | None,
    notional: float,
    quantity: float | None,
    reference_price: float | None,
    setup: dict[str, Any],
    risk: dict[str, Any],
    path: Path = LEDGER_PATH,
) -> dict[str, Any]:
    return append_ledger_event(
        {
            "event": "paper_entry",
            "broker": broker,
            "scope": scope,
            "symbol": symbol.upper(),
            "order_id": order_id,
            "order_status": order_status,
            "notional": round(float(notional), 4),
            "quantity": round(float(quantity), 8) if quantity is not None else None,
            "reference_price": round(float(reference_price), 6) if reference_price is not None else None,
            "setup": setup,
            "risk": risk,
            "real_cash": False,
            "promotion_evidence": True,
        },
        path,
    )


def record_exit(
    *,
    broker: str,
    scope: str,
    symbol: str,
    order_id: str | None,
    order_status: str | None,
    quantity: float,
    entry_reference_price: float,
    exit_reference_price: float,
    exit_reason: str,
    path: Path = LEDGER_PATH,
) -> dict[str, Any]:
    pnl_dollars = (float(exit_reference_price) - float(entry_reference_price)) * float(quantity)
    pnl_pct = (float(exit_reference_price) - float(entry_reference_price)) / float(entry_reference_price) if entry_reference_price > 0 else 0.0
    return append_ledger_event(
        {
            "event": "paper_exit",
            "broker": broker,
            "scope": scope,
            "symbol": symbol.upper(),
            "order_id": order_id,
            "order_status": order_status,
            "quantity": round(float(quantity), 8),
            "entry_reference_price": round(float(entry_reference_price), 6),
            "exit_reference_price": round(float(exit_reference_price), 6),
            "exit_reason": exit_reason,
            "pnl_dollars": round(pnl_dollars, 4),
            "pnl_pct": round(pnl_pct, 6),
            "real_cash": False,
            "promotion_evidence": True,
        },
        path,
    )


def _date_key(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 else "unknown"


def _profit_factor(closed: list[dict[str, Any]]) -> float | None:
    gains = sum(max(0.0, as_float(item.get("pnl_dollars"))) for item in closed)
    losses = abs(sum(min(0.0, as_float(item.get("pnl_dollars"))) for item in closed))
    if losses <= 0:
        return None if gains <= 0 else float("inf")
    return gains / losses


def _max_drawdown_pct(closed: list[dict[str, Any]], starting_equity: float = 100000.0) -> float:
    equity = float(starting_equity)
    peak = equity
    max_drawdown = 0.0
    for item in sorted(closed, key=lambda row: str(row.get("timestamp") or "")):
        equity += as_float(item.get("pnl_dollars"))
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown * 100.0


def promotion_eligible_closed_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    open_entries: defaultdict[tuple[str, str, str], int] = defaultdict(int)
    eligible: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: str(item.get("timestamp") or "")):
        key = (
            str(row.get("broker") or ""),
            str(row.get("scope") or ""),
            str(row.get("symbol") or "").upper(),
        )
        if row.get("event") == "paper_entry":
            open_entries[key] += 1
        elif row.get("event") == "paper_exit" and open_entries[key] > 0:
            open_entries[key] -= 1
            eligible.append(row)
    return eligible


def summarize(path: Path = LEDGER_PATH, gates_path: Path = READINESS_GATES_PATH) -> dict[str, Any]:
    rows = read_ledger(path)
    entries = [row for row in rows if row.get("event") == "paper_entry"]
    exits = [row for row in rows if row.get("event") == "paper_exit"]
    eligible_exits = promotion_eligible_closed_trades(rows)
    symbol_counts = Counter(str(row.get("symbol") or "UNKNOWN") for row in entries)
    exit_reason_counts = Counter(str(row.get("exit_reason") or "UNKNOWN") for row in eligible_exits)
    dates = sorted({_date_key(row.get("timestamp")) for row in eligible_exits if _date_key(row.get("timestamp")) != "unknown"})
    pnl_values = [as_float(row.get("pnl_dollars")) for row in eligible_exits]
    wins = [value for value in pnl_values if value > 0]
    losses = [value for value in pnl_values if value < 0]
    profit_factor = _profit_factor(eligible_exits)
    max_drawdown_pct = _max_drawdown_pct(eligible_exits)
    gates = json.loads(gates_path.read_text(encoding="utf-8")).get("required_before_limited_autonomous_live", {})
    profit_factor_passes = (
        profit_factor == float("inf")
        or (profit_factor is not None and profit_factor >= float(gates.get("min_profit_factor_after_costs", 1.2)))
    )
    gate_checks = {
        "min_closed_paper_trades": len(eligible_exits) >= int(gates.get("min_closed_paper_trades", 100)),
        "min_distinct_market_days": len(dates) >= int(gates.get("min_distinct_market_days", 20)),
        "min_profit_factor_after_costs": profit_factor_passes,
        "max_paper_drawdown_pct": max_drawdown_pct <= float(gates.get("max_paper_drawdown_pct", 8.0)),
        "min_trade_journal_coverage_pct": all(row.get("promotion_evidence") for row in entries + eligible_exits),
    }
    blockers = [name for name, passed in gate_checks.items() if not passed]
    return {
        "status": "PAPER_PROMOTION_READY" if not blockers else "PAPER_PROMOTION_BLOCKED",
        "ledger_path": str(path),
        "entry_count": len(entries),
        "closed_trade_count": len(exits),
        "promotion_eligible_closed_trade_count": len(eligible_exits),
        "unpaired_exit_count": max(0, len(exits) - len(eligible_exits)),
        "distinct_closed_trade_days": len(dates),
        "total_pnl_dollars": round(sum(pnl_values), 4),
        "win_rate": round(len(wins) / len(exits), 4) if exits else 0.0,
        "average_win_dollars": round(sum(wins) / len(wins), 4) if wins else 0.0,
        "average_loss_dollars": round(sum(losses) / len(losses), 4) if losses else 0.0,
        "profit_factor_after_costs": "INF" if profit_factor == float("inf") else round(profit_factor or 0.0, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "top_symbols": dict(symbol_counts.most_common(10)),
        "exit_reasons": dict(exit_reason_counts),
        "gate_checks": gate_checks,
        "blockers": blockers,
        "required_gates": gates,
        "review_only": True,
        "can_place_order_from_this_report": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize paper lifecycle ledger promotion evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)
    report = summarize()
    print(json.dumps(report, indent=2, sort_keys=True, default=str) if args.json else report)
    return 0 if report["status"] == "PAPER_PROMOTION_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
