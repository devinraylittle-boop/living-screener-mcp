from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from app.mcp_server import (
    _build_manual_trade_desk,
    _build_manual_trade_preflight_ticket,
    _close_manual_option_paper_trade,
    _export_journal_checkpoint,
    _get_data_truth_cockpit,
    _get_event_radar,
    _get_event_volatility_playbook,
    _get_ops_command_center,
    _get_market_session_playbook,
    _get_session_risk_guard,
    _get_system_communication_audit,
    _get_failure_mode_audit,
    _get_tomorrow_operator_brief,
    _get_trading_day_launch_checklist,
    _log_manual_option_paper_entry,
    _log_manual_broker_action,
    _market_readiness_check,
    _review_candidate_for_options,
    _restore_journal_checkpoint,
    _run_broad_opportunity_scan,
    _run_event_volatility_scan,
    _run_autonomous_morning_scan,
    _run_go_live_rehearsal,
    _run_live_review_cycle,
    _run_market_open_observer,
    _run_morning_readiness_autopilot,
    _run_observer_followup,
    _run_trading_day_heartbeat,
    _run_latest_harvest_followup,
    _run_review_harvest,
    _summarize_trading_day_alerts,
    _summarize_manual_option_paper_trades,
    _watch_manual_option_position,
    container,
)
from app.version import BUILD_VERSION


ROOT = Path(__file__).resolve().parents[1]


def _tickers(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    symbols = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return symbols or None


def _float_or_none(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _int_or_default(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _review_only_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "build_version": BUILD_VERSION,
        "review_only": True,
        "can_place_order_from_this_mcp": False,
        "can_cancel_order_from_this_mcp": False,
        **payload,
    }


def _wants_html(request: Request) -> bool:
    requested_format = (request.query_params.get("format") or "").lower()
    if requested_format == "json":
        return False
    if requested_format == "html":
        return True
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "auto"}


def _release_manifest_payload() -> dict[str, Any]:
    manifest_path = ROOT / "RELEASE_MANIFEST.json"
    fallback = {
        "service": "Living Screener MCP",
        "target_build_version": BUILD_VERSION,
        "expected_live_tool_count": None,
        "manifest_loaded": False,
    }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        manifest = fallback
    return _review_only_envelope({"status": "RELEASE_MANIFEST_READY", "manifest": manifest})


def _html_page(title: str, body: str, payload: dict[str, Any], extra_head: str = "") -> HTMLResponse:
    raw_json = escape(json.dumps(payload, indent=2, sort_keys=True, default=str))
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {extra_head}
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --ink: #15171a;
      --muted: #626a73;
      --line: #d9dde3;
      --ok: #116b41;
      --warn: #9a5b00;
      --bad: #9d1f2f;
      --chip: #eef1f5;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; letter-spacing: 0; }}
    p {{ color: var(--muted); margin: 0 0 16px; }}
    .topbar {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
      margin-bottom: 20px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--chip);
      font-weight: 650;
      white-space: nowrap;
    }}
    .badge.ok {{ color: var(--ok); background: #e7f5ee; }}
    .badge.warn {{ color: var(--warn); background: #fff3db; }}
    .badge.bad {{ color: var(--bad); background: #fde8eb; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 12px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .label {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 3px; }}
    .value {{ font-weight: 650; overflow-wrap: anywhere; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      text-align: left;
      vertical-align: top;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
    }}
    th {{ color: var(--muted); font-size: 12px; font-weight: 650; background: #fbfcfd; }}
    tr:last-child td {{ border-bottom: 0; }}
    ul {{ margin: 8px 0 0 18px; padding: 0; }}
    li {{ margin: 5px 0; }}
    input, select, button {{
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 8px 10px;
      font: inherit;
    }}
    button {{
      width: auto;
      min-width: 190px;
      border-color: #15171a;
      background: #15171a;
      color: #fff;
      font-weight: 650;
      cursor: pointer;
    }}
    pre {{
      overflow: auto;
      padding: 14px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #101317;
      color: #e7edf5;
      font-size: 12px;
    }}
    details {{ margin-top: 20px; }}
    summary {{ cursor: pointer; color: var(--muted); font-weight: 650; }}
  </style>
</head>
<body>
  <main>{body}
    <details>
      <summary>Raw JSON</summary>
      <pre>{raw_json}</pre>
    </details>
  </main>
</body>
</html>"""
    return HTMLResponse(html)


def _field_grid(items: list[tuple[str, Any]]) -> str:
    cells = []
    for label, value in items:
        shown = "None" if value is None else value
        cells.append(
            f'<div class="panel"><span class="label">{escape(str(label))}</span>'
            f'<span class="value">{escape(str(shown))}</span></div>'
        )
    return f'<div class="grid">{"".join(cells)}</div>'


def _status_class(status: str | None) -> str:
    value = (status or "").upper()
    if value in {"REVIEW_ONLY_OPTIONS_READY", "SMALL_ACCOUNT_SCALP_ACCEPTABLE", "OPTIONS_CHAIN_ACCEPTABLE", "EVENT_VOLATILITY_PLAYBOOK_READY", "EVENT_OPTIONS_READY", "EVENT_RADAR_READY", "BROAD_OPTIONS_READY", "DATA_TRUTH_READY", "SYSTEM_COMMUNICATION_AUDIT_READY"}:
        return "ok"
    if value in {"NO_TRADE_PLAN", "NO_SMALL_ACCOUNT_CONTRACT", "EVENT_NO_TRADE_PLAN", "BROAD_NO_TRADE_PLAN", "DATA_TRUTH_BLOCKED"}:
        return "bad"
    return "warn"


def _list(items: list[Any]) -> str:
    if not items:
        return "<p>None.</p>"
    return "<ul>" + "".join(f"<li>{escape(str(item))}</li>" for item in items) + "</ul>"


def _contract_table(contracts: list[dict[str, Any]], title: str) -> str:
    if not contracts:
        return f"<h2>{escape(title)}</h2><p>None.</p>"
    rows = []
    for contract in contracts:
        reasons = contract.get("reasons") or []
        rows.append(
            "<tr>"
            f"<td>{escape(str(contract.get('contract_symbol') or ''))}</td>"
            f"<td>{escape(str(contract.get('expiration') or ''))}</td>"
            f"<td>{escape(str(contract.get('strike') or ''))}</td>"
            f"<td>{escape(str(contract.get('days_to_expiration') or ''))}</td>"
            f"<td>{escape(str(contract.get('bid') or ''))} / {escape(str(contract.get('ask') or ''))}</td>"
            f"<td>{escape(str(contract.get('spread_pct') or ''))}</td>"
            f"<td>{escape(str(contract.get('volume') or ''))} / {escape(str(contract.get('open_interest') or ''))}</td>"
            f"<td>{escape('; '.join(str(reason) for reason in reasons))}</td>"
            f"<td>{escape(str(contract.get('closest_to_pass_reason') or ''))}</td>"
            "</tr>"
        )
    return f"""
<h2>{escape(title)}</h2>
<table>
  <thead>
    <tr><th>Contract</th><th>Exp.</th><th>Strike</th><th>DTE</th><th>Bid / Ask</th><th>Spread</th><th>Vol / OI</th><th>Reasons</th><th>Closest To Pass</th></tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>"""


def _options_review_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    stock = result.get("stock_setup") or {}
    signals = stock.get("key_signals") or {}
    options = result.get("options_chain_validation") or {}
    small = result.get("small_account_review") or {}
    selected = small.get("selected_contract") or {}
    friction = small.get("friction_adjusted_review") or {}
    friction_components = friction.get("components") or {}
    setup_memory = result.get("setup_memory") or {}
    fingerprint = setup_memory.get("fingerprint") or {}
    lesson_summary = setup_memory.get("similar_lesson_summary") or {}
    review_summary = setup_memory.get("similar_review_summary") or {}
    status = result.get("status")
    small_status = small.get("status")
    option_status = options.get("status")
    ticker = result.get("ticker") or stock.get("ticker") or "Option Review"
    body = f"""
<div class="topbar">
  <div>
    <h1>{escape(str(ticker))} Options Review</h1>
    <p>{escape(str(result.get('reason') or 'Review-only options candidate check.'))}</p>
  </div>
  <div>
    <span class="badge {_status_class(status)}">{escape(str(status or 'UNKNOWN'))}</span>
  </div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Review Only", payload.get("review_only")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
    ("Options Chain", option_status),
    ("Small Account Scalp", small_status),
    ("Priority Score", small.get("priority_score")),
    ("Friction Score", small.get("friction_adjusted_score")),
    ("Friction Band", small.get("friction_band")),
])}
<h2>Stock Setup</h2>
{_field_grid([
    ("Ticker", stock.get("ticker")),
    ("Stock Status", stock.get("status")),
    ("Score", stock.get("score")),
    ("Direction", stock.get("direction")),
    ("RVOL", signals.get("relative_volume")),
    ("RVOL Status", signals.get("relative_volume_status")),
    ("Above VWAP", signals.get("above_vwap")),
    ("Below VWAP", signals.get("below_vwap")),
    ("VWAP", signals.get("vwap")),
])}
<h2>Selected Contract</h2>
{_field_grid([
    ("Contract", selected.get("contract_symbol")),
    ("Expiration", selected.get("expiration")),
    ("Strike", selected.get("strike")),
    ("DTE", selected.get("days_to_expiration")),
    ("Bid", selected.get("bid")),
    ("Ask", selected.get("ask")),
    ("Spread", selected.get("spread_pct")),
    ("Volume", selected.get("volume")),
    ("Open Interest", selected.get("open_interest")),
    ("Max Loss", selected.get("max_loss_dollars")),
    ("Est. Round-Trip Slippage", friction_components.get("estimated_round_trip_slippage_dollars")),
    ("Slippage % Max Loss", friction_components.get("slippage_pct_of_max_loss")),
])}
<h2>Friction Review</h2>
{_field_grid([
    ("Score", friction.get("score")),
    ("Band", friction.get("band")),
    ("Absolute Spread", friction_components.get("absolute_spread")),
    ("Volume", friction_components.get("volume")),
    ("Open Interest", friction_components.get("open_interest")),
])}
{_list([f"{item.get('name')}: {item.get('reason')}" for item in (friction.get("penalties") or [])])}
<h2>Setup Memory</h2>
{_field_grid([
    ("Memory Signal", setup_memory.get("memory_signal")),
    ("Similar Reviews", review_summary.get("sample_size")),
    ("Similar Lessons", lesson_summary.get("sample_size")),
    ("Avg Similar Return", lesson_summary.get("average_directional_return")),
    ("Setup Key", fingerprint.get("setup_key")),
])}
{_list(fingerprint.get("tags") or [])}
<h2>Warnings</h2>
{_list(result.get("warnings") or small.get("warnings") or [])}
{_contract_table(options.get("best_rejected_contracts") or [], "Best Rejected Contracts")}
"""
    return _html_page(f"{ticker} Options Review", body, payload)


def _learning_dashboard_html(payload: dict[str, Any]) -> HTMLResponse:
    classifications = payload.get("recent_classifications") or []
    proposals = payload.get("recent_rule_proposals") or []
    counts = payload.get("classification_counts") or {}
    rows = []
    for item in classifications:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('classification') or ''))}</td>"
            f"<td>{escape(str(item.get('direction') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_score') or ''))}</td>"
            f"<td>{escape(', '.join(str(tag) for tag in item.get('lesson_tags', [])))}</td>"
            f"<td>{escape(str(item.get('reason') or ''))}</td>"
            "</tr>"
        )
    proposal_rows = []
    for proposal_event in proposals:
        for proposal in (proposal_event.get("proposals") or []):
            proposal_rows.append(
                "<tr>"
                f"<td>{escape(str(proposal.get('tag') or ''))}</td>"
                f"<td>{escape(str(proposal.get('action') or ''))}</td>"
                f"<td>{escape(str(proposal.get('sample_size') or ''))}</td>"
                f"<td>{escape(str(proposal.get('confidence') or ''))}</td>"
                f"<td>{escape(str(proposal.get('thesis') or ''))}</td>"
                "</tr>"
            )
    body = f"""
<div class="topbar">
  <div>
    <h1>Learning Dashboard</h1>
    <p>Research memory for false positives, missed moves, good passes, and rule-change hypotheses.</p>
  </div>
  <div><span class="badge ok">REVIEW ONLY</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Recent Classifications", len(classifications)),
    ("Recent Rule Proposal Events", len(proposals)),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
    ("Do Not Auto Apply", True),
])}
<h2>Classification Counts</h2>
{_field_grid([(key, value) for key, value in counts.items()] or [("None", 0)])}
<h2>Recent Lessons</h2>
<table>
  <thead>
    <tr><th>Ticker</th><th>Lesson</th><th>Direction</th><th>Score</th><th>Tags</th><th>Reason</th></tr>
  </thead>
  <tbody>{''.join(rows) if rows else '<tr><td colspan="6">No lessons logged yet.</td></tr>'}</tbody>
</table>
<h2>Rule Proposals</h2>
<table>
  <thead>
    <tr><th>Tag</th><th>Action</th><th>Samples</th><th>Confidence</th><th>Thesis</th></tr>
  </thead>
  <tbody>{''.join(proposal_rows) if proposal_rows else '<tr><td colspan="5">No proposal has enough evidence yet.</td></tr>'}</tbody>
</table>
"""
    return _html_page("Learning Dashboard", body, payload)


def _failure_mode_audit_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    controls = result.get("controls") or []
    rows = []
    for item in controls:
        covered_by = "; ".join(str(value) for value in item.get("covered_by", []))
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('area') or ''))}</td>"
            f"<td><span class=\"badge {_status_class(item.get('status'))}\">{escape(str(item.get('status') or ''))}</span></td>"
            f"<td>{escape(covered_by)}</td>"
            f"<td>{escape(str(item.get('remaining_gap') or ''))}</td>"
            f"<td>{escape(str(item.get('next_hardening') or ''))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Failure-Mode Audit</h1>
    <p>Maps known trading-system failure modes to current controls, gaps, and the next hardening step.</p>
  </div>
  <div><span class="badge ok">REVIEW ONLY</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Source", result.get("source")),
    ("Tool Count Observed", result.get("tool_count_observed")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
    ("Can Cancel Orders", payload.get("can_cancel_order_from_this_mcp")),
])}
<h2>Control Summary</h2>
{_field_grid([(str(key).replace('_', ' ').title(), value) for key, value in (result.get("control_summary") or {}).items()])}
<h2>Controls And Gaps</h2>
<table>
  <thead>
    <tr><th>Area</th><th>Status</th><th>Covered By</th><th>Remaining Gap</th><th>Next Hardening</th></tr>
  </thead>
  <tbody>{''.join(rows) if rows else '<tr><td colspan="5">No controls returned.</td></tr>'}</tbody>
</table>
<h2>Blocked Until Proven</h2>
{_list(result.get("blocked_until") or [])}
<h2>Highest Priority Next</h2>
{_list(result.get("highest_priority_next") or [])}
"""
    return _html_page("Failure-Mode Audit", body, payload)


def _global_scan_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    rows = []
    combined = (result.get("top_candidates") or []) + (result.get("watch_list") or []) + (result.get("pass_list") or [])
    for item in combined:
        features = item.get("feature_summary") or {}
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('symbol') or ''))}</td>"
            f"<td>{escape(str(item.get('status') or ''))}</td>"
            f"<td>{escape(str(item.get('score') or ''))}</td>"
            f"<td>{escape(str(item.get('direction') or ''))}</td>"
            f"<td>{escape(str(features.get('relative_volume') or ''))}</td>"
            f"<td>{escape(str(features.get('range_expansion') or ''))}</td>"
            f"<td>{escape(str(features.get('compression_break') or ''))}</td>"
            f"<td>{escape(', '.join(str(tag) for tag in item.get('lesson_tags', [])))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Off-Hours Research Scan</h1>
    <p>Underlying-only movement study for crypto and global instruments. No options chain or broker action.</p>
  </div>
  <div><span class="badge ok">RESEARCH ONLY</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Market", result.get("market")),
    ("Period", result.get("period")),
    ("Interval", result.get("interval")),
    ("Top Candidates", len(result.get("top_candidates") or [])),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Results</h2>
<table>
  <thead>
    <tr><th>Symbol</th><th>Status</th><th>Score</th><th>Direction</th><th>RVOL</th><th>Range Exp.</th><th>Compression Break</th><th>Tags</th></tr>
  </thead>
  <tbody>{''.join(rows) if rows else '<tr><td colspan="8">No scan rows returned.</td></tr>'}</tbody>
</table>
"""
    return _html_page("Off-Hours Research Scan", body, payload)


def _crypto_backtest_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    aggregate = result.get("aggregate") or {}
    rows = []
    for item in result.get("results") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('symbol') or ''))}</td>"
            f"<td>{escape(str(item.get('symbol_recommendation') or item.get('status') or ''))}</td>"
            f"<td>{escape(str(item.get('trade_count') or 0))}</td>"
            f"<td>{escape(str(item.get('win_rate') or 0))}</td>"
            f"<td>{escape(str(item.get('return_pct') or 0))}</td>"
            f"<td>{escape(str(item.get('max_drawdown_pct') or 0))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Crypto Paper Backtest</h1>
    <p>Paper-only crypto research. No broker execution, no background worker.</p>
  </div>
  <div><span class="badge ok">{escape(str(result.get('result') or 'PAPER ONLY'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Period", result.get("period")),
    ("Interval", result.get("interval")),
    ("Best Symbol", result.get("best_symbol")),
    ("Aggregate Return", aggregate.get("aggregate_return_pct")),
    ("Total Trades", aggregate.get("total_trade_count")),
    ("Win Rate", aggregate.get("win_rate")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Symbols</h2>
<table>
  <thead>
    <tr><th>Symbol</th><th>Recommendation</th><th>Trades</th><th>Win Rate</th><th>Return</th><th>Max Drawdown</th></tr>
  </thead>
  <tbody>{''.join(rows) if rows else '<tr><td colspan="6">No results returned.</td></tr>'}</tbody>
</table>
"""
    return _html_page("Crypto Paper Backtest", body, payload)


def _review_harvest_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    rows = []
    for item in result.get("ranked_candidates") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('status') or ''))}</td>"
            f"<td>{escape(str(item.get('direction') or ''))}</td>"
            f"<td>{escape(str(item.get('score') or ''))}</td>"
            f"<td>{escape(str(item.get('priority_score') or ''))}</td>"
            f"<td>{escape(str(item.get('friction_adjusted_score') or ''))}</td>"
            f"<td>{escape(str(item.get('contract') or ''))}</td>"
            f"<td>{escape(str(item.get('ask') or ''))} / {escape(str(item.get('max_loss_dollars') or ''))}</td>"
            f"<td>{escape(str(item.get('memory_signal') or ''))}</td>"
            "</tr>"
        )
    watch_rows = []
    for item in result.get("watch_only") or []:
        watch_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('status') or ''))}</td>"
            f"<td>{escape(str(item.get('reason') or ''))}</td>"
            f"<td>{escape('; '.join(str(warning) for warning in item.get('warnings', [])))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Review Harvest</h1>
    <p>Review-only scan harvest. Ranks only candidates passing stock setup and small-account options gates.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Mode", result.get("mode")),
    ("Reviewed", result.get("reviewed_count")),
    ("Eligible", result.get("eligible_count")),
    ("Watch Only", result.get("watch_only_count")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Ranked Candidates</h2>
<table>
  <thead>
    <tr><th>Ticker</th><th>Status</th><th>Direction</th><th>Stock Score</th><th>Priority</th><th>Friction</th><th>Contract</th><th>Ask / Max Loss</th><th>Memory</th></tr>
  </thead>
  <tbody>{''.join(rows) if rows else '<tr><td colspan="9">No eligible ranked candidates.</td></tr>'}</tbody>
</table>
<h2>Watch Only</h2>
<table>
  <thead>
    <tr><th>Ticker</th><th>Status</th><th>Reason</th><th>Warnings</th></tr>
  </thead>
  <tbody>{''.join(watch_rows) if watch_rows else '<tr><td colspan="4">No watch-only reviews.</td></tr>'}</tbody>
</table>
"""
    return _html_page("Review Harvest", body, payload)


def _session_playbook_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    rows = []
    for block in result.get("session_blocks") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(str(block.get('central_time') or ''))}</td>"
            f"<td>{escape(str(block.get('label') or ''))}</td>"
            f"<td>{escape(str(block.get('intent') or ''))}</td>"
            f"<td>{escape('; '.join(str(action) for action in block.get('actions', [])))}</td>"
            f"<td>{escape(str(block.get('pass_condition') or ''))}</td>"
            f"<td>{escape(str(block.get('fail_condition') or ''))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Market Session Playbook</h1>
    <p>{escape(str(result.get('target') or 'Review-only live market workflow.'))}</p>
  </div>
  <div><span class="badge ok">REVIEW ONLY</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Generated", result.get("generated_at")),
    ("Universe", ', '.join(result.get("universe") or [])),
    ("Account Ref.", result.get("account_value_reference")),
    ("Contract Cap", result.get("small_account_contract_cap")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Session Blocks</h2>
<table>
  <thead>
    <tr><th>CT</th><th>Block</th><th>Intent</th><th>Actions</th><th>Pass</th><th>Fail</th></tr>
  </thead>
  <tbody>{''.join(rows) if rows else '<tr><td colspan="6">No playbook blocks returned.</td></tr>'}</tbody>
</table>
<h2>Manual Trade Gate</h2>
{_list(result.get("manual_trade_gate") or [])}
"""
    return _html_page("Market Session Playbook", body, payload)


def _event_volatility_playbook_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    lane_rows = []
    for lane in result.get("lanes") or []:
        applies = lane.get("applies_to")
        if isinstance(applies, list):
            applies = ", ".join(str(item) for item in applies[:10]) + ("..." if len(applies) > 10 else "")
        lane_rows.append(
            "<tr>"
            f"<td>{escape(str(lane.get('lane') or ''))}</td>"
            f"<td>{escape(str(applies or ''))}</td>"
            f"<td>{escape(str(lane.get('rule') or ''))}</td>"
            f"<td>{escape(str(lane.get('do_not_do') or ''))}</td>"
            "</tr>"
        )
    timeline_rows = []
    for item in result.get("tomorrow_timeline_central") or []:
        timeline_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('time') or ''))}</td>"
            f"<td>{escape(str(item.get('action') or ''))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Event Volatility Playbook</h1>
    <p>{escape(str(result.get('mission') or 'Event-day review plan.'))}</p>
  </div>
  <div><span class="badge ok">REVIEW ONLY</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Event", result.get("event_name")),
    ("Direct Symbol", result.get("direct_symbol")),
    ("Contract Cap", result.get("small_account_contract_cap")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Decision Lanes</h2>
<table><thead><tr><th>Lane</th><th>Applies To</th><th>Rule</th><th>Do Not Do</th></tr></thead><tbody>{''.join(lane_rows)}</tbody></table>
<h2>Timeline</h2>
<table><thead><tr><th>Central Time</th><th>Action</th></tr></thead><tbody>{''.join(timeline_rows)}</tbody></table>
<h2>Hard No-Trade Gates</h2>
{_list(result.get("hard_no_trade_gates") or [])}
<h2>Stock vs Options</h2>
{_list(result.get("stock_vs_options_decision") or [])}
"""
    return _html_page("Event Volatility Playbook", body, payload)


def _event_volatility_scan_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    option_rows = []
    for item in result.get("ranked_options_candidates") or []:
        option_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_direction') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_score') or ''))}</td>"
            f"<td>{escape(str(item.get('relative_volume') or ''))}</td>"
            f"<td>{escape(str(item.get('vwap_state') or ''))}</td>"
            f"<td>{escape(str(item.get('selected_contract') or ''))}</td>"
            f"<td>{escape(str(item.get('dte') or ''))}</td>"
            f"<td>{escape(str(item.get('ask') or ''))} / {escape(str(item.get('max_loss_dollars') or ''))}</td>"
            f"<td>{escape(str(item.get('priority_score') or ''))}</td>"
            "</tr>"
        )
    stock_rows = []
    for item in result.get("stock_review_candidates") or []:
        stock_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('lane') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_direction') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_score') or ''))}</td>"
            f"<td>{escape(str(item.get('relative_volume') or ''))}</td>"
            f"<td>{escape(str(item.get('vwap_state') or ''))}</td>"
            f"<td>{escape('; '.join(str(reason) for reason in (item.get('why_not_ranked') or [])))}</td>"
            "</tr>"
        )
    reject_rows = []
    for item in result.get("watch_only_or_rejected") or []:
        reject_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('lane') or ''))}</td>"
            f"<td>{escape(str(item.get('option_status') or item.get('stock_status') or ''))}</td>"
            f"<td>{escape('; '.join(str(reason) for reason in (item.get('why_not_ranked') or [])))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Event Volatility Scan</h1>
    <p>{escape(str(result.get('next_action') or 'Review-only event scan.'))}</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Event", result.get("event_name")),
    ("Direct Symbol", result.get("direct_symbol")),
    ("Direct Status", result.get("direct_symbol_status")),
    ("Stock Candidates", result.get("stock_candidate_count")),
    ("Options Reviews", result.get("options_review_count")),
    ("Contract Cap", result.get("max_contract_price_used")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Ranked Options Candidates</h2>
<table><thead><tr><th>Ticker</th><th>Direction</th><th>Score</th><th>RVOL</th><th>VWAP</th><th>Contract</th><th>DTE</th><th>Ask / Max Loss</th><th>Priority</th></tr></thead><tbody>{''.join(option_rows) or '<tr><td colspan="9">None.</td></tr>'}</tbody></table>
<h2>Stock Review Lanes</h2>
<table><thead><tr><th>Ticker</th><th>Lane</th><th>Direction</th><th>Score</th><th>RVOL</th><th>VWAP</th><th>Why Not Options Ranked</th></tr></thead><tbody>{''.join(stock_rows) or '<tr><td colspan="7">None.</td></tr>'}</tbody></table>
<h2>Watch Only / Rejected</h2>
<table><thead><tr><th>Ticker</th><th>Lane</th><th>Status</th><th>Reason</th></tr></thead><tbody>{''.join(reject_rows) or '<tr><td colspan="4">None.</td></tr>'}</tbody></table>
"""
    return _html_page("Event Volatility Scan", body, payload)


def _event_radar_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    event_rows = []
    for event in result.get("active_events") or []:
        event_rows.append(
            "<tr>"
            f"<td>{escape(str(event.get('label') or ''))}</td>"
            f"<td>{escape(str(event.get('expected_date') or ''))}</td>"
            f"<td>{escape(str(event.get('direct_symbol') or ''))}</td>"
            f"<td>{escape(str(event.get('confidence') or ''))}</td>"
            f"<td>{escape(str(event.get('primary_risk') or ''))}</td>"
            "</tr>"
        )
    lane_rows = []
    for lane in result.get("radar_lanes") or []:
        lane_rows.append(
            "<tr>"
            f"<td>{escape(str(lane.get('lane') or ''))}</td>"
            f"<td>{escape(', '.join(str(item) for item in (lane.get('examples') or [])))}</td>"
            f"<td>{escape(str(lane.get('current_status') or ''))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Event Radar</h1>
    <p>{escape(str(result.get('mission') or 'Catalyst radar with anti-tunnel-vision rules.'))}</p>
  </div>
  <div><span class="badge ok">REVIEW ONLY</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Active Events", len(result.get("active_events") or [])),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Active Events</h2>
<table><thead><tr><th>Event</th><th>Date</th><th>Direct Symbol</th><th>Confidence</th><th>Primary Risk</th></tr></thead><tbody>{''.join(event_rows) or '<tr><td colspan="5">None.</td></tr>'}</tbody></table>
<h2>Radar Lanes</h2>
<table><thead><tr><th>Lane</th><th>Examples</th><th>Status</th></tr></thead><tbody>{''.join(lane_rows) or '<tr><td colspan="3">None.</td></tr>'}</tbody></table>
<h2>Anti-Tunnel-Vision Rules</h2>
{_list(result.get("anti_tunnel_vision_rules") or [])}
"""
    return _html_page("Event Radar", body, payload)


def _broad_opportunity_scan_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    option_rows = []
    for item in result.get("ranked_options_candidates") or []:
        option_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_direction') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_score') or ''))}</td>"
            f"<td>{escape(str(item.get('relative_volume') or ''))}</td>"
            f"<td>{escape(str(item.get('vwap_state') or ''))}</td>"
            f"<td>{escape(str(item.get('selected_contract') or ''))}</td>"
            f"<td>{escape(str(item.get('ask') or ''))} / {escape(str(item.get('max_loss_dollars') or ''))}</td>"
            f"<td>{escape(str(item.get('priority_score') or ''))}</td>"
            f"<td>{escape(str(item.get('event_related') or False))}</td>"
            "</tr>"
        )
    stock_rows = []
    for item in result.get("stock_review_candidates") or []:
        stock_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('lane') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_direction') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_score') or ''))}</td>"
            f"<td>{escape(str(item.get('relative_volume') or ''))}</td>"
            f"<td>{escape(str(item.get('event_related') or False))}</td>"
            f"<td>{escape('; '.join(str(reason) for reason in (item.get('why_not_ranked') or [])))}</td>"
            "</tr>"
        )
    micro_rows = []
    for item in result.get("microcap_paper_research") or []:
        micro_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_direction') or ''))}</td>"
            f"<td>{escape(str(item.get('stock_score') or ''))}</td>"
            f"<td>{escape(str(item.get('relative_volume') or ''))}</td>"
            f"<td>{escape('; '.join(str(reason) for reason in (item.get('why_not_ranked') or [])))}</td>"
            "</tr>"
        )
    crypto = result.get("crypto_research_lane") or {}
    body = f"""
<div class="topbar">
  <div>
    <h1>Broad Opportunity Scan</h1>
    <p>{escape(str(result.get('next_action') or 'Broad review-only opportunity scan.'))}</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Universe Count", result.get("universe_count")),
    ("Stock Candidates", result.get("stock_candidate_count")),
    ("Options Reviews", result.get("options_review_count")),
    ("Event Candidates", result.get("event_candidate_count")),
    ("Non-Event Candidates", result.get("non_event_candidate_count")),
    ("Contract Cap", result.get("max_contract_price_used")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Ranked Options Candidates</h2>
<table><thead><tr><th>Ticker</th><th>Direction</th><th>Score</th><th>RVOL</th><th>VWAP</th><th>Contract</th><th>Ask / Max Loss</th><th>Priority</th><th>Event?</th></tr></thead><tbody>{''.join(option_rows) or '<tr><td colspan="9">None.</td></tr>'}</tbody></table>
<h2>Stock Review Fallbacks</h2>
<table><thead><tr><th>Ticker</th><th>Lane</th><th>Direction</th><th>Score</th><th>RVOL</th><th>Event?</th><th>Reason</th></tr></thead><tbody>{''.join(stock_rows) or '<tr><td colspan="7">None.</td></tr>'}</tbody></table>
<h2>Microcap Paper Research</h2>
<table><thead><tr><th>Ticker</th><th>Direction</th><th>Score</th><th>RVOL</th><th>Reason</th></tr></thead><tbody>{''.join(micro_rows) or '<tr><td colspan="5">None.</td></tr>'}</tbody></table>
<h2>Crypto Research Lane</h2>
{_field_grid([
    ("Status", crypto.get("status")),
    ("Symbols", ', '.join(crypto.get("symbols") or [])),
    ("Reason", crypto.get("reason")),
])}
"""
    return _html_page("Broad Opportunity Scan", body, payload)


def _data_truth_cockpit_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    health = result.get("market_data_health") or {}
    rows = []
    for row in health.get("rows") or []:
        rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('ticker') or ''))}</td>"
            f"<td>{escape(str(row.get('status') or ''))}</td>"
            f"<td>{escape(str(row.get('quote_age_seconds') or ''))}</td>"
            f"<td>{escape(str(row.get('candle_age_seconds') or ''))}</td>"
            f"<td>{escape(str(row.get('quote_provider') or ''))}</td>"
            f"<td>{escape(str(row.get('candle_provider') or ''))}</td>"
            f"<td>{escape('; '.join(str(reason) for reason in (row.get('blocking_reasons') or [])))}</td>"
            "</tr>"
        )
    level2 = result.get("robinhood_level_2_decision") or {}
    body = f"""
<div class="topbar">
  <div>
    <h1>Data Truth Cockpit</h1>
    <p>{escape(str(result.get('next_action') or 'Live input quality and truth-source status.'))}</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Market Data Status", health.get("status")),
    ("Provider", health.get("provider")),
    ("Healthy", health.get("healthy_count")),
    ("Degraded", health.get("degraded_count")),
    ("Options Truth", (result.get("options_truth") or {}).get("real_money_options_truth_status")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Market Data Rows</h2>
<table><thead><tr><th>Ticker</th><th>Status</th><th>Quote Age Sec</th><th>Candle Age Sec</th><th>Quote Provider</th><th>Candle Provider</th><th>Reasons</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="7">None.</td></tr>'}</tbody></table>
<h2>Source Priority</h2>
{_list(result.get("source_priority") or [])}
<h2>Robinhood Level II Decision</h2>
{_field_grid([
    ("Recommendation", level2.get("recommendation")),
    ("Reason", level2.get("reason")),
])}
{_list(level2.get("subscribe_when") or [])}
<h2>Cash Test Readiness</h2>
{_list((result.get("cash_test_readiness") or {}).get("real_cash_allowed_only_after") or [])}
"""
    return _html_page("Data Truth Cockpit", body, payload)


def _system_communication_audit_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    map_rows = []
    for item in result.get("communication_map") or []:
        map_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('system') or ''))}</td>"
            f"<td>{escape(', '.join(str(value) for value in (item.get('writes') or [])))}</td>"
            f"<td>{escape(', '.join(str(value) for value in (item.get('read_by') or [])))}</td>"
            f"<td>{escape(str(item.get('clutter_control') or ''))}</td>"
            "</tr>"
        )
    count_rows = []
    for event_type, count in sorted((result.get("recent_event_type_counts") or {}).items()):
        count_rows.append(
            "<tr>"
            f"<td>{escape(str(event_type))}</td>"
            f"<td>{escape(str(count))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>System Communication Audit</h1>
    <p>{escape(str(result.get('next_action') or 'Checks whether the machine shares useful data without creating clutter.'))}</p>
  </div>
  <div><span class="badge ok">REVIEW ONLY</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Recent Events", result.get("recent_event_count")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Communication Map</h2>
<table><thead><tr><th>System</th><th>Writes</th><th>Read By</th><th>Clutter Control</th></tr></thead><tbody>{''.join(map_rows)}</tbody></table>
<h2>Recent Event Counts</h2>
<table><thead><tr><th>Event Type</th><th>Count</th></tr></thead><tbody>{''.join(count_rows) or '<tr><td colspan="2">None.</td></tr>'}</tbody></table>
<h2>Clutter Limits</h2>
{_list(result.get("clutter_limits") or [])}
<h2>Known Weak Links</h2>
{_list(result.get("known_weak_links") or [])}
"""
    return _html_page("System Communication Audit", body, payload)


def _harvest_followup_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    outcome_rows = []
    for item in result.get("outcomes") or []:
        outcome_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('verdict') or item.get('status') or ''))}</td>"
            f"<td>{escape(str(item.get('current_return_pct') or ''))}</td>"
            f"<td>{escape(str(item.get('max_favorable_excursion') or ''))}</td>"
            f"<td>{escape(str(item.get('max_adverse_excursion') or ''))}</td>"
            f"<td>{escape(str(item.get('reason') or item.get('outcome_window_status') or ''))}</td>"
            "</tr>"
        )
    class_rows = []
    for item in result.get("classifications") or []:
        class_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('classification') or ''))}</td>"
            f"<td>{escape(str(item.get('reason') or ''))}</td>"
            f"<td>{escape(', '.join(str(tag) for tag in item.get('lesson_tags', [])))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Harvest Follow-Up</h1>
    <p>Outcome checks and learning labels from the latest review-only harvest.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Harvest Event", result.get("harvest_event_id")),
    ("Checks Requested", result.get("checks_requested")),
    ("Checks Completed", result.get("checks_completed")),
    ("Classify", result.get("classify")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Outcomes</h2>
<table>
  <thead>
    <tr><th>Ticker</th><th>Verdict</th><th>Return</th><th>MFE</th><th>MAE</th><th>Note</th></tr>
  </thead>
  <tbody>{''.join(outcome_rows) if outcome_rows else '<tr><td colspan="6">No outcomes checked.</td></tr>'}</tbody>
</table>
<h2>Learning Labels</h2>
<table>
  <thead>
    <tr><th>Ticker</th><th>Classification</th><th>Reason</th><th>Tags</th></tr>
  </thead>
  <tbody>{''.join(class_rows) if class_rows else '<tr><td colspan="4">No classifications logged.</td></tr>'}</tbody>
</table>
"""
    return _html_page("Harvest Follow-Up", body, payload)


def _command_center_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    latest = result.get("latest") or {}
    action_links = result.get("action_links") or {}
    latest_rows = []
    for label, item in latest.items():
        latest_rows.append(
            "<tr>"
            f"<td>{escape(str(label))}</td>"
            f"<td>{escape(str((item or {}).get('status') if item else 'none'))}</td>"
            f"<td>{escape(str((item or {}).get('timestamp') if item else ''))}</td>"
            f"<td>{escape(str((item or {}).get('eligible_count') if item else ''))}</td>"
            f"<td>{escape(str((item or {}).get('next_step') if item else ''))}</td>"
            "</tr>"
        )
    link_rows = []
    for label, href in action_links.items():
        link_rows.append(
            "<tr>"
            f"<td>{escape(str(label))}</td>"
            f"<td><a href=\"{escape(str(href))}\">{escape(str(href))}</a></td>"
            "</tr>"
        )
    labels = []
    for item in result.get("latest_learning_labels") or []:
        labels.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('classification') or ''))}</td>"
            f"<td>{escape(', '.join(str(tag) for tag in item.get('lesson_tags', [])))}</td>"
            f"<td>{escape(str(item.get('reason') or ''))}</td>"
            "</tr>"
        )
    next_action = result.get("next_action") or {}
    body = f"""
<div class="topbar">
  <div>
    <h1>Ops Command Center</h1>
    <p>One-page review-only state summary for readiness, harvest, follow-up, and learning.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Universe", ', '.join(result.get("universe") or [])),
    ("Next Action", next_action.get("label")),
    ("Reason", next_action.get("reason")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
    ("Can Cancel Orders", payload.get("can_cancel_order_from_this_mcp")),
])}
<h2>Latest Loop State</h2>
<table>
  <thead>
    <tr><th>Area</th><th>Status</th><th>Timestamp</th><th>Eligible</th><th>Next Step</th></tr>
  </thead>
  <tbody>{''.join(latest_rows) if latest_rows else '<tr><td colspan="5">No loop state logged yet.</td></tr>'}</tbody>
</table>
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>URL</th></tr></thead>
  <tbody>{''.join(link_rows)}</tbody>
</table>
<h2>Latest Learning Labels</h2>
<table>
  <thead><tr><th>Ticker</th><th>Classification</th><th>Tags</th><th>Reason</th></tr></thead>
  <tbody>{''.join(labels) if labels else '<tr><td colspan="4">No learning labels logged yet.</td></tr>'}</tbody>
</table>
<h2>Manual Trade Gate</h2>
{_list(result.get("manual_trade_gate") or [])}
"""
    return _html_page("Ops Command Center", body, payload)


def _trading_day_launch_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    latest = result.get("latest") or {}
    session_risk = (latest.get("session_risk_guard") or {}) if isinstance(latest, dict) else {}
    sequence_rows = []
    for item in result.get("launch_sequence") or []:
        sequence_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('phase') or ''))}</td>"
            f"<td>{escape(str(item.get('go_condition') or ''))}</td>"
            f"<td><a href=\"{escape(str(item.get('primary_link') or ''))}\">{escape(str(item.get('primary_link') or ''))}</a></td>"
            f"<td>{escape(str(item.get('stop_if') or ''))}</td>"
            "</tr>"
        )
    latest_rows = []
    for label, item in latest.items():
        latest_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td>{escape(str((item or {}).get('status') if isinstance(item, dict) else ''))}</td>"
            f"<td>{escape(str((item or {}).get('timestamp') if isinstance(item, dict) else ''))}</td>"
            f"<td>{escape(str((item or {}).get('next_step') or (item or {}).get('next_action') if isinstance(item, dict) else ''))}</td>"
            "</tr>"
        )
    action_rows = []
    for label, url in (result.get("action_links") or {}).items():
        action_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Trading Day Launch</h1>
    <p>Tomorrow's go/no-go operating map. Follow gates one at a time; PASS is the default when anything is unclear.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Next Action", result.get("next_action")),
    ("Session Risk", session_risk.get("status")),
    ("Universe", result.get("universe")),
    ("Account Ref.", result.get("account_value_reference")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Latest Logged State</h2>
<table>
  <thead><tr><th>Event</th><th>Status</th><th>Timestamp</th><th>Next</th></tr></thead>
  <tbody>{''.join(latest_rows) if latest_rows else '<tr><td colspan="4">No launch state logged yet.</td></tr>'}</tbody>
</table>
<h2>Launch Sequence</h2>
<table>
  <thead><tr><th>Phase</th><th>Go Condition</th><th>Link</th><th>Stop If</th></tr></thead>
  <tbody>{''.join(sequence_rows)}</tbody>
</table>
<h2>Absolute No-Trade Rules</h2>
{_list(result.get("absolute_no_trade_rules") or [])}
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(action_rows)}</tbody>
</table>
"""
    return _html_page("Trading Day Launch", body, payload)


def _tomorrow_operator_brief_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    session_risk = result.get("session_risk_guard") or {}
    paper_ledger = result.get("paper_ledger") or {}
    connector = result.get("chatgpt_connector_fallback") or {}
    sequence_rows = []
    for item in result.get("morning_sequence") or []:
        link = str(item.get("link") or "")
        sequence_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('step') or ''))}</td>"
            f"<td>{escape(str(item.get('target_time_ct') or ''))}</td>"
            f"<td><a href=\"{escape(link)}\">{escape(link)}</a></td>"
            f"<td>{escape(str(item.get('pass_condition') or ''))}</td>"
            "</tr>"
        )
    schedule_rows = []
    for item in result.get("session_schedule_ct") or []:
        schedule_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('time') or ''))}</td>"
            f"<td>{escape(str(item.get('focus') or ''))}</td>"
            "</tr>"
        )
    latest_rows = []
    for label, item in (result.get("latest") or {}).items():
        latest_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td>{escape(str((item or {}).get('status') if isinstance(item, dict) else ''))}</td>"
            f"<td>{escape(str((item or {}).get('timestamp') if isinstance(item, dict) else ''))}</td>"
            f"<td>{escape(str((item or {}).get('next_action') or (item or {}).get('next_step') if isinstance(item, dict) else ''))}</td>"
            "</tr>"
        )
    action_rows = []
    for label, url in (result.get("action_links") or {}).items():
        action_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    validation_rows = []
    for url in connector.get("validation_urls") or []:
        validation_rows.append(
            "<tr>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Tomorrow Operator Brief</h1>
    <p>One review-only start page for tomorrow: safety, session risk, pages to open, connector fallback, and hard stops.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Next Action", result.get("next_action")),
    ("Universe", ', '.join(result.get("universe") or [])),
    ("Account Ref.", result.get("account_value_reference")),
    ("Contract Cap", result.get("small_account_contract_cap")),
    ("Session Risk", session_risk.get("status")),
    ("Paper Open", paper_ledger.get("open_count")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Morning Sequence</h2>
<table>
  <thead><tr><th>Step</th><th>Time CT</th><th>Link</th><th>Pass Condition</th></tr></thead>
  <tbody>{''.join(sequence_rows)}</tbody>
</table>
<h2>Session Schedule</h2>
<table>
  <thead><tr><th>Time CT</th><th>Focus</th></tr></thead>
  <tbody>{''.join(schedule_rows)}</tbody>
</table>
<h2>Session Risk And Paper Ledger</h2>
{_field_grid([
    ("Risk Status", session_risk.get("status")),
    ("Open Positions", session_risk.get("open_position_count")),
    ("Open Risk", session_risk.get("open_risk_dollars")),
    ("Closed P/L", session_risk.get("closed_pnl_dollars")),
    ("Risk Next Action", session_risk.get("next_action")),
    ("Paper Ledger", paper_ledger.get("status")),
    ("Paper Entries", paper_ledger.get("entry_count")),
    ("Paper Win Rate", paper_ledger.get("win_rate")),
])}
<h2>Latest Logged State</h2>
<table>
  <thead><tr><th>Event</th><th>Status</th><th>Timestamp</th><th>Next</th></tr></thead>
  <tbody>{''.join(latest_rows) if latest_rows else '<tr><td colspan="4">No operator state logged yet.</td></tr>'}</tbody>
</table>
<h2>Manual Trade Gate</h2>
{_list(result.get("manual_trade_gate") or [])}
<h2>Absolute No-Trade Rules</h2>
{_list(result.get("absolute_no_trade_rules") or [])}
<h2>Connector Fallback</h2>
<p>{escape(str(connector.get('short_status') or ''))}</p>
<table>
  <thead><tr><th>Validation URL</th></tr></thead>
  <tbody>{''.join(validation_rows)}</tbody>
</table>
<h2>Fallback Prompt</h2>
<pre>{escape(str(connector.get("prompt") or ""))}</pre>
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(action_rows)}</tbody>
</table>
<h2>Notes</h2>
{_list(result.get("notes") or [])}
"""
    return _html_page("Tomorrow Operator Brief", body, payload)


def _go_live_rehearsal_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    operator = result.get("operator_brief") or {}
    readiness = result.get("market_readiness") or {}
    live_rows = []
    for item in result.get("required_live_urls") or []:
        url = str(item.get("url") or "")
        live_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('label') or ''))}</td>"
            f"<td><a href=\"{escape(url)}\">{escape(url)}</a></td>"
            f"<td>{escape(str(item.get('expected') or ''))}</td>"
            "</tr>"
        )
    tab_rows = []
    for item in result.get("tomorrow_open_tabs") or []:
        url = str(item.get("url") or "")
        tab_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('label') or ''))}</td>"
            f"<td><a href=\"{escape(url)}\">{escape(url)}</a></td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Go-Live Rehearsal</h1>
    <p>Deployment and operating-readiness rehearsal for tomorrow. Review-only; no scans unless requested, no trade plans, no broker action.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Next Action", result.get("next_action")),
    ("Market Check Included", result.get("include_market_check")),
    ("Operator Brief", operator.get("status")),
    ("Session Risk", operator.get("session_risk_status")),
    ("Paper Open", operator.get("paper_open_count")),
    ("Readiness", readiness.get("status")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Blocking Reasons</h2>
{_list(result.get("blocking_reasons") or ["None"])}
<h2>Warnings</h2>
{_list(result.get("warnings") or ["None"])}
<h2>Live Validation URLs</h2>
<table>
  <thead><tr><th>Check</th><th>URL</th><th>Expected</th></tr></thead>
  <tbody>{''.join(live_rows)}</tbody>
</table>
<h2>Tomorrow Tabs</h2>
<table>
  <thead><tr><th>Tab</th><th>URL</th></tr></thead>
  <tbody>{''.join(tab_rows)}</tbody>
</table>
<h2>Manual Trade Gate</h2>
{_list(result.get("manual_trade_gate") or [])}
<h2>Absolute No-Trade Rules</h2>
{_list(result.get("absolute_no_trade_rules") or [])}
<h2>Notes</h2>
{_list(result.get("notes") or [])}
"""
    return _html_page("Go-Live Rehearsal", body, payload)


def _trading_day_heartbeat_html(payload: dict[str, Any], auto_refresh: bool = False) -> HTMLResponse:
    result = payload.get("result") or {}
    phase = result.get("phase") or {}
    operation = result.get("operation_result") or {}
    refresh_seconds = max(60, min(int(result.get("next_refresh_seconds") or 300), 1800))
    extra_head = f'<meta http-equiv="refresh" content="{refresh_seconds}">' if auto_refresh else ""
    monitor_banner = (
        f"<p><strong>Monitor mode:</strong> this page refreshes every {refresh_seconds} seconds while the tab stays open.</p>"
        if auto_refresh
        else ""
    )
    action_rows = []
    for label, url in (result.get("action_links") or {}).items():
        action_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Trading Day Heartbeat</h1>
    <p>One safe cadence tick: observe, review, or learn based on market phase. Review-only.</p>
    {monitor_banner}
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Phase", phase.get("phase")),
    ("ET Time", phase.get("now_et")),
    ("Operation", result.get("operation")),
    ("Operation Status", result.get("operation_status")),
    ("Next Refresh Seconds", result.get("next_refresh_seconds")),
    ("Pending Recheck Required", result.get("pending_recheck_required")),
    ("Next Action", result.get("next_action")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Operation Summary</h2>
{_field_grid([
    ("Event ID", operation.get("id")),
    ("Timestamp", operation.get("timestamp")),
    ("Status", operation.get("status")),
    ("Mode", operation.get("mode")),
    ("Candidates", operation.get("candidate_count")),
    ("Eligible", operation.get("eligible_count")),
    ("Reviewed", operation.get("reviewed_count")),
    ("Next Step", operation.get("next_step")),
])}
<h2>Absolute No-Trade Rules</h2>
{_list(result.get("absolute_no_trade_rules") or [])}
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(action_rows)}</tbody>
</table>
<h2>Notes</h2>
{_list(result.get("notes") or [])}
"""
    return _html_page("Trading Day Heartbeat", body, payload, extra_head=extra_head)


def _autonomous_morning_scan_html(payload: dict[str, Any], auto_refresh: bool = False) -> HTMLResponse:
    result = payload.get("result") or {}
    phase = result.get("phase") or {}
    health = result.get("market_data_health") or {}
    truth = result.get("truth_source") or {}
    catalysts = result.get("catalyst_context") or {}
    heartbeat = result.get("heartbeat") or {}
    refresh_seconds = max(60, min(int(result.get("next_refresh_seconds") or 300), 1800))
    extra_head = f'<meta http-equiv="refresh" content="{refresh_seconds}">' if auto_refresh else ""
    monitor_banner = (
        f"<p><strong>Autonomous monitor:</strong> this page refreshes every {refresh_seconds} seconds while the tab stays open.</p>"
        if auto_refresh
        else ""
    )
    link_rows = []
    for label, url in (result.get("action_links") or {}).items():
        link_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    block_rows = []
    for item in catalysts.get("blocks") or []:
        block_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('status') or ''))}</td>"
            f"<td>{escape('; '.join(str(reason) for reason in item.get('blocking_reasons', [])))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Autonomous Morning Scan</h1>
    <p>Phase-aware review-only scanner loop. It observes, logs, and escalates manual-review candidates without broker action.</p>
    {monitor_banner}
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Phase", phase.get("phase")),
    ("ET Time", phase.get("now_et")),
    ("Next Refresh Seconds", result.get("next_refresh_seconds")),
    ("Next Action", result.get("next_action")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
    ("Can Cancel Orders", payload.get("can_cancel_order_from_this_mcp")),
])}
<h2>Truth And Data Gates</h2>
{_field_grid([
    ("Truth Source", truth.get("status")),
    ("Market Data", health.get("status")),
    ("Healthy Rows", health.get("healthy_count")),
    ("Degraded Rows", health.get("degraded_count")),
    ("Catalyst Checked", catalysts.get("checked_count")),
    ("Catalyst Blocks", catalysts.get("blocked_or_unavailable_count")),
    ("Heartbeat", heartbeat.get("status")),
])}
<h2>Cash Readiness</h2>
{_field_grid([(str(key).replace('_', ' ').title(), value) for key, value in (result.get("cash_readiness") or {}).items()])}
<h2>Catalyst Blocks</h2>
<table>
  <thead><tr><th>Ticker</th><th>Status</th><th>Reasons</th></tr></thead>
  <tbody>{''.join(block_rows) if block_rows else '<tr><td colspan="3">None.</td></tr>'}</tbody>
</table>
<h2>Hard Stops</h2>
{_list(result.get("hard_stops") or [])}
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(link_rows)}</tbody>
</table>
<h2>Notes</h2>
{_list(result.get("notes") or [])}
"""
    return _html_page("Autonomous Morning Scan", body, payload, extra_head=extra_head)


def _trading_day_alerts_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    alert_rows = []
    for alert in result.get("alerts") or []:
        link = str(alert.get("link") or "")
        alert_rows.append(
            "<tr>"
            f"<td>{escape(str(alert.get('level') or ''))}</td>"
            f"<td>{escape(str(alert.get('type') or ''))}</td>"
            f"<td>{escape(str(alert.get('title') or ''))}</td>"
            f"<td>{escape(str(alert.get('timestamp') or ''))}</td>"
            f"<td>{escape(str(alert.get('next_action') or ''))}</td>"
            f"<td><a href=\"{escape(link)}\">{escape(link)}</a></td>"
            "</tr>"
        )
    link_rows = []
    for label, url in (result.get("action_links") or {}).items():
        link_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Trading Day Alerts</h1>
    <p>Attention queue from recent heartbeat, live-cycle, manual-action, and checkpoint events. Review-only.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Top Level", result.get("top_level")),
    ("Alert Count", result.get("alert_count")),
    ("Next Action", result.get("next_action")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Alerts</h2>
<table>
  <thead><tr><th>Level</th><th>Type</th><th>Title</th><th>Time</th><th>Next Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(alert_rows) if alert_rows else '<tr><td colspan="6">No attention alerts.</td></tr>'}</tbody>
</table>
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(link_rows)}</tbody>
</table>
<h2>Notes</h2>
{_list(result.get("notes") or [])}
"""
    return _html_page("Trading Day Alerts", body, payload)


def _morning_autopilot_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    readiness = result.get("readiness") or {}
    ledger = result.get("paper_ledger") or {}
    session_risk = result.get("session_risk_guard") or {}
    action_links = result.get("action_links") or {}
    link_rows = []
    for label, url in action_links.items():
        link_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    session_rows = []
    for block in result.get("session_blocks") or []:
        session_rows.append(
            "<tr>"
            f"<td>{escape(str(block.get('central_time') or ''))}</td>"
            f"<td>{escape(str(block.get('label') or ''))}</td>"
            f"<td>{escape(str(block.get('intent') or ''))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Morning Readiness Autopilot</h1>
    <p>Build/safety, data readiness, paper ledger, and next action for the live review loop.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Next Action", result.get("next_action")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
    ("Can Cancel Orders", payload.get("can_cancel_order_from_this_mcp")),
])}
<h2>Readiness</h2>
{_field_grid([
    ("Readiness Status", readiness.get("status")),
    ("Data Status", readiness.get("data_status")),
    ("Candidates", readiness.get("candidate_count")),
    ("Valid Rows", readiness.get("valid_row_count")),
    ("Quote Problems", readiness.get("quote_problem_count")),
])}
<h2>Paper Ledger</h2>
{_field_grid([
    ("Ledger Status", ledger.get("status")),
    ("Entries", ledger.get("entry_count")),
    ("Open", ledger.get("open_count")),
    ("Closed", ledger.get("closed_count")),
    ("Win Rate", ledger.get("win_rate")),
    ("Total P/L", ledger.get("total_pnl_dollars")),
])}
<h2>Session Risk Guard</h2>
{_field_grid([
    ("Session Risk Status", session_risk.get("status")),
    ("Open Positions", session_risk.get("open_position_count")),
    ("Open Risk", session_risk.get("open_risk_dollars")),
    ("Closed P/L", session_risk.get("closed_pnl_dollars")),
    ("Next Action", session_risk.get("next_action")),
])}
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(link_rows)}</tbody>
</table>
<h2>Session Blocks</h2>
<table>
  <thead><tr><th>Central Time</th><th>Block</th><th>Intent</th></tr></thead>
  <tbody>{''.join(session_rows) if session_rows else '<tr><td colspan="3">No session blocks available.</td></tr>'}</tbody>
</table>
<h2>Manual Trade Gate</h2>
{_list(result.get("manual_trade_gate") or [])}
"""
    return _html_page("Morning Readiness Autopilot", body, payload)


def _live_review_cycle_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    readiness = result.get("readiness") or {}
    harvest = result.get("harvest") or {}
    ledger = result.get("paper_ledger") or {}
    session_risk = result.get("session_risk_guard") or {}
    candidate_rows = []
    for item in result.get("ranked_candidates") or []:
        selected = item.get("selected_contract") or {}
        small = item.get("small_account_review") or {}
        stock = item.get("stock_setup") or {}
        candidate_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or stock.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('direction') or stock.get('direction') or ''))}</td>"
            f"<td>{escape(str((stock.get('score') if isinstance(stock, dict) else '') or ''))}</td>"
            f"<td>{escape(str(small.get('priority_score') or ''))}</td>"
            f"<td>{escape(str(selected.get('contract_symbol') or ''))}</td>"
            f"<td>{escape(str(selected.get('ask') or ''))}</td>"
            f"<td>{escape(str(selected.get('max_loss_dollars') or ''))}</td>"
            f"<td>{escape(str(item.get('status') or ''))}</td>"
            "</tr>"
        )
    watch_rows = []
    for item in result.get("watch_only_reviews") or []:
        watch_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('status') or ''))}</td>"
            f"<td>{escape(str(item.get('reason') or ''))}</td>"
            "</tr>"
        )
    action_rows = []
    for label, url in (result.get("action_links") or {}).items():
        action_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Live Review Cycle</h1>
    <p>Market-hours scan, options review harvest, paper ledger state, and next manual action.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Next Action", result.get("next_action")),
    ("Manual Preflight Required", result.get("manual_preflight_required")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Readiness And Harvest</h2>
{_field_grid([
    ("Readiness", readiness.get("status")),
    ("Data Status", readiness.get("data_status")),
    ("Valid Rows", readiness.get("valid_row_count")),
    ("Quote Problems", readiness.get("quote_problem_count")),
    ("Harvest", harvest.get("status")),
    ("Reviewed", harvest.get("reviewed_count")),
    ("Eligible", harvest.get("eligible_count")),
    ("Watch Only", harvest.get("watch_only_count")),
])}
<h2>Ranked Candidates</h2>
<table>
  <thead><tr><th>Ticker</th><th>Direction</th><th>Stock Score</th><th>Priority</th><th>Contract</th><th>Ask</th><th>Max Loss</th><th>Status</th></tr></thead>
  <tbody>{''.join(candidate_rows) if candidate_rows else '<tr><td colspan="8">No candidate cleared both stock and small-account options gates.</td></tr>'}</tbody>
</table>
<h2>Watch Only Reviews</h2>
<table>
  <thead><tr><th>Ticker</th><th>Status</th><th>Reason</th></tr></thead>
  <tbody>{''.join(watch_rows) if watch_rows else '<tr><td colspan="3">No watch-only reviews in this cycle.</td></tr>'}</tbody>
</table>
<h2>Paper Ledger</h2>
{_field_grid([
    ("Ledger", ledger.get("status")),
    ("Entries", ledger.get("entry_count")),
    ("Open", ledger.get("open_count")),
    ("Closed", ledger.get("closed_count")),
    ("Win Rate", ledger.get("win_rate")),
    ("Total P/L", ledger.get("total_pnl_dollars")),
])}
<h2>Session Risk Guard</h2>
{_field_grid([
    ("Session Risk Status", session_risk.get("status")),
    ("Open Positions", session_risk.get("open_position_count")),
    ("Open Risk", session_risk.get("open_risk_dollars")),
    ("Proposed Risk", session_risk.get("proposed_risk_dollars")),
    ("Projected Open Risk", session_risk.get("projected_open_risk_dollars")),
    ("Next Action", session_risk.get("next_action")),
])}
<h2>Manual Trade Gate</h2>
{_list(result.get("manual_trade_gate") or [])}
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(action_rows)}</tbody>
</table>
"""
    return _html_page("Live Review Cycle", body, payload)


def _market_open_observer_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    evidence = result.get("evidence_summary") or {}
    delta = result.get("delta_vs_previous_observer") or {}
    candidate_rows = []
    for item in result.get("candidate_observations") or []:
        candidate_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('direction') or ''))}</td>"
            f"<td>{escape(str(item.get('score') or ''))}</td>"
            f"<td>{escape(str(item.get('relative_volume') or ''))}</td>"
            f"<td>{escape(str(item.get('vwap_state') or ''))}</td>"
            f"<td>{escape(str(item.get('relative_strength_label') or ''))}</td>"
            f"<td>{escape(str(item.get('data_confidence') or ''))}</td>"
            f"<td>{escape(', '.join(str(flag) for flag in item.get('data_flags', [])[:4]))}</td>"
            "</tr>"
        )
    pass_rows = []
    for item in result.get("pass_observations") or []:
        pass_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('score') or ''))}</td>"
            f"<td>{escape(str(item.get('direction') or ''))}</td>"
            f"<td>{escape(str(item.get('primary_reason') or ''))}</td>"
            "</tr>"
        )
    action_rows = []
    for label, url in (result.get("action_links") or {}).items():
        action_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Market Open Observer</h1>
    <p>Evidence capture for opening-window scans. No options review, no trade plan, no broker action.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Next Action", result.get("next_action")),
    ("Cadence Minutes", result.get("cadence_minutes")),
    ("Candidates", result.get("candidate_count")),
    ("Pass Count", result.get("pass_count")),
    ("Valid Rows", result.get("valid_row_count")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Evidence Quality</h2>
{_field_grid([
    ("Packet Count", result.get("evidence_packet_count")),
    ("Evidence Batch ID", result.get("evidence_batch_event_id")),
    ("Confidence Counts", evidence.get("data_confidence_counts")),
    ("Top Data Flags", evidence.get("top_data_flags")),
    ("Recommendation", evidence.get("recommendation")),
])}
<h2>Delta Versus Previous Refresh</h2>
{_field_grid([
    ("Delta Status", delta.get("status")),
    ("New Candidates", delta.get("new_candidate_tickers")),
    ("Dropped Candidates", delta.get("dropped_candidate_tickers")),
    ("Persistent Candidates", delta.get("persistent_candidate_tickers")),
])}
<h2>Stock Candidate Observations</h2>
<table>
  <thead><tr><th>Ticker</th><th>Direction</th><th>Score</th><th>RVOL</th><th>VWAP</th><th>Rel. Strength</th><th>Data Conf.</th><th>Flags</th></tr></thead>
  <tbody>{''.join(candidate_rows) if candidate_rows else '<tr><td colspan="8">No stock candidates in this observer refresh.</td></tr>'}</tbody>
</table>
<h2>Pass Observations</h2>
<table>
  <thead><tr><th>Ticker</th><th>Score</th><th>Direction</th><th>Primary Reason</th></tr></thead>
  <tbody>{''.join(pass_rows) if pass_rows else '<tr><td colspan="4">No pass rows returned.</td></tr>'}</tbody>
</table>
<h2>Observer Rules</h2>
{_list(result.get("observer_rules") or [])}
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(action_rows)}</tbody>
</table>
"""
    return _html_page("Market Open Observer", body, payload)


def _observer_followup_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    outcome_rows = []
    for item in result.get("outcomes") or []:
        outcome_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('source_bucket') or ''))}</td>"
            f"<td>{escape(str(item.get('direction') or ''))}</td>"
            f"<td>{escape(str(item.get('current_return_pct') or ''))}</td>"
            f"<td>{escape(str(item.get('max_favorable_excursion') or ''))}</td>"
            f"<td>{escape(str(item.get('max_adverse_excursion') or ''))}</td>"
            f"<td>{escape(str(item.get('verdict') or item.get('status') or ''))}</td>"
            "</tr>"
        )
    class_rows = []
    for item in result.get("classifications") or []:
        class_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('classification') or ''))}</td>"
            f"<td>{escape(str(item.get('direction') or ''))}</td>"
            f"<td>{escape(', '.join(str(tag) for tag in item.get('lesson_tags', [])))}</td>"
            f"<td>{escape(str(item.get('reason') or ''))}</td>"
            "</tr>"
        )
    action_rows = []
    for label, url in (result.get("action_links") or {}).items():
        action_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Observer Follow-Up</h1>
    <p>Grades previous observer candidates and pass rows to find missed moves, good passes, and rule-learning evidence.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Next Action", result.get("next_action")),
    ("Items Checked", result.get("items_checked")),
    ("Missed Moves", result.get("missed_move_count")),
    ("Good Passes", result.get("good_pass_count")),
    ("Unavailable", result.get("outcome_unavailable_count")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Outcomes</h2>
<table>
  <thead><tr><th>Ticker</th><th>Source</th><th>Direction</th><th>Current Return</th><th>MFE</th><th>MAE</th><th>Verdict</th></tr></thead>
  <tbody>{''.join(outcome_rows) if outcome_rows else '<tr><td colspan="7">No observer outcomes available yet.</td></tr>'}</tbody>
</table>
<h2>Learning Labels</h2>
<table>
  <thead><tr><th>Ticker</th><th>Classification</th><th>Direction</th><th>Tags</th><th>Reason</th></tr></thead>
  <tbody>{''.join(class_rows) if class_rows else '<tr><td colspan="5">No learning labels generated yet.</td></tr>'}</tbody>
</table>
<h2>Notes</h2>
{_list(result.get("notes") or [])}
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(action_rows)}</tbody>
</table>
"""
    return _html_page("Observer Follow-Up", body, payload)


def _manual_preflight_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    ticket = result.get("manual_ticket") or {}
    selected = result.get("selected_contract") or {}
    option_validation = result.get("option_validation") or {}
    risk = result.get("risk_check") or {}
    body = f"""
<div class="topbar">
  <div>
    <h1>Manual Trade Preflight</h1>
    <p>Broker-visible option snapshot validation, risk check, and manual review ticket.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Ticker", result.get("ticker")),
    ("Direction", result.get("direction")),
    ("Account Ref.", result.get("account_value_reference")),
    ("Options Gate", option_validation.get("status")),
    ("Risk Gate", risk.get("status")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Ticket</h2>
{_field_grid([
    ("Contract", ticket.get("contract_symbol")),
    ("Order Type", ticket.get("order_type")),
    ("Max Review Ask", ticket.get("max_review_ask")),
    ("Max Loss", ticket.get("max_loss_dollars")),
    ("Quantity", ticket.get("quantity")),
    ("Broker Action Required", ticket.get("broker_action_required")),
    ("MCP Can Execute", ticket.get("mcp_can_execute")),
])}
<h2>Contract Snapshot</h2>
{_field_grid([
    ("Bid", selected.get("bid")),
    ("Ask", selected.get("ask")),
    ("Spread", selected.get("spread_pct")),
    ("Volume", selected.get("volume")),
    ("Open Interest", selected.get("open_interest")),
    ("DTE", selected.get("days_to_expiration")),
    ("Strike", selected.get("strike")),
])}
<h2>Blocking Reasons</h2>
{_list(result.get("blocking_reasons") or [])}
<h2>Warnings</h2>
{_list(result.get("warnings") or [])}
<h2>Checklist</h2>
{_list(result.get("checklist") or [])}
"""
    return _html_page("Manual Trade Preflight", body, payload)


def _manual_trade_desk_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    preflight = result.get("preflight") or {}
    session_risk = result.get("session_risk_guard") or {}
    ticket = preflight.get("manual_ticket") or {}
    selected = preflight.get("selected_contract") or {}
    paper_request = result.get("paper_entry_request") or {}
    paper_payload = paper_request.get("payload") or {}
    checkpoint = result.get("checkpoint_request") or {}
    body = f"""
<div class="topbar">
  <div>
    <h1>Manual Trade Desk</h1>
    <p>Broker snapshot preflight, paper-entry payload, and checkpoint reminder. Review-only.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Ticker", result.get("ticker")),
    ("Direction", result.get("direction")),
    ("Contract", result.get("contract_symbol")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Preflight</h2>
{_field_grid([
    ("Preflight Status", preflight.get("status")),
    ("Options Gate", (preflight.get("option_validation") or {}).get("status")),
    ("Risk Gate", (preflight.get("risk_check") or {}).get("status")),
    ("Order Type", ticket.get("order_type")),
    ("Max Review Ask", ticket.get("max_review_ask")),
    ("Max Loss", ticket.get("max_loss_dollars")),
])}
<h2>Session Risk Guard</h2>
{_field_grid([
    ("Session Risk Status", session_risk.get("status")),
    ("Open Positions", f"{session_risk.get('open_position_count')} / {session_risk.get('max_open_positions')}"),
    ("Open Risk", session_risk.get("open_risk_dollars")),
    ("Proposed Risk", session_risk.get("proposed_risk_dollars")),
    ("Projected Open Risk", session_risk.get("projected_open_risk_dollars")),
    ("Closed P/L", session_risk.get("closed_pnl_dollars")),
    ("Next Action", session_risk.get("next_action")),
])}
<h2>Contract Snapshot</h2>
{_field_grid([
    ("Bid", selected.get("bid")),
    ("Ask", selected.get("ask")),
    ("Spread", selected.get("spread_pct")),
    ("Volume", selected.get("volume")),
    ("Open Interest", selected.get("open_interest")),
    ("DTE", selected.get("days_to_expiration")),
    ("Strike", selected.get("strike")),
])}
<h2>Paper Entry Payload</h2>
{_field_grid([
    ("Endpoint", paper_request.get("endpoint")),
    ("Fill Price", paper_payload.get("fill_price")),
    ("Quantity", paper_payload.get("quantity")),
    ("Underlying Ref.", paper_payload.get("underlying_price")),
])}
<h2>Checkpoint</h2>
{_field_grid([
    ("Endpoint", checkpoint.get("endpoint")),
    ("When", checkpoint.get("when")),
])}
<h2>Blocking Reasons</h2>
{_list(result.get("blocking_reasons") or preflight.get("blocking_reasons") or [])}
<h2>Warnings</h2>
{_list(result.get("warnings") or preflight.get("warnings") or [])}
<h2>Next Steps</h2>
{_list(result.get("next_steps") or [])}
"""
    return _html_page("Manual Trade Desk", body, payload)


def _manual_snapshot_form_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    body = f"""
<div class="topbar">
  <div>
    <h1>Manual Snapshot Form</h1>
    <p>Enter broker-visible option fields, then submit to the manual trade desk. Review-only; this form cannot place, submit, modify, simulate, or cancel orders.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Destination", "/trade/manual-desk"),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<form method="get" action="/trade/manual-desk" class="panel">
  <input type="hidden" name="format" value="html">
  <div class="grid">
    <label class="panel"><span class="label">Ticker</span><input name="ticker" required placeholder="SOFI"></label>
    <label class="panel"><span class="label">Contract Symbol</span><input name="contract_symbol" required placeholder="SOFI260612P00015000"></label>
    <label class="panel"><span class="label">Expected Contract Symbol</span><input name="expected_contract_symbol" placeholder="from MCP review, if available"></label>
    <label class="panel"><span class="label">Broker Snapshot Time</span><input name="broker_snapshot_ts" required placeholder="2026-06-11T14:35:00Z"></label>
    <label class="panel"><span class="label">Option Quote Time</span><input name="option_quote_ts" required placeholder="2026-06-11T14:35:00Z"></label>
    <label class="panel"><span class="label">Direction</span>
      <select name="direction">
        <option value="put">put</option>
        <option value="call">call</option>
      </select>
    </label>
    <label class="panel"><span class="label">Bid</span><input name="bid" required type="number" min="0" step="0.01" placeholder="0.04"></label>
    <label class="panel"><span class="label">Ask</span><input name="ask" required type="number" min="0" step="0.01" placeholder="0.05"></label>
    <label class="panel"><span class="label">Bid Size</span><input name="bid_size" type="number" min="0" step="1" placeholder="10"></label>
    <label class="panel"><span class="label">Ask Size</span><input name="ask_size" type="number" min="0" step="1" placeholder="10"></label>
    <label class="panel"><span class="label">Volume</span><input name="volume" required type="number" min="0" step="1" placeholder="500"></label>
    <label class="panel"><span class="label">Open Interest</span><input name="open_interest" required type="number" min="0" step="1" placeholder="2000"></label>
    <label class="panel"><span class="label">DTE</span><input name="dte" required type="number" min="0" step="1" placeholder="3"></label>
    <label class="panel"><span class="label">Strike</span><input name="strike" required type="number" min="0" step="0.5" placeholder="15"></label>
    <label class="panel"><span class="label">Expiration</span><input name="expiration" placeholder="2026-06-12"></label>
    <label class="panel"><span class="label">Multiplier</span><input name="multiplier" type="number" min="1" step="1" value="100"></label>
    <label class="panel"><span class="label">Deliverable</span><input name="deliverable" value="100 shares"></label>
    <label class="panel"><span class="label">Underlying Price</span><input name="underlying_price" type="number" min="0" step="0.01" placeholder="16.50"></label>
    <label class="panel"><span class="label">Underlying VWAP</span><input name="underlying_vwap" type="number" min="0" step="0.01" placeholder="16.80"></label>
    <label class="panel"><span class="label">Account Value Ref.</span><input name="account_value" type="number" min="0" step="0.01" value="50"></label>
    <label class="panel"><span class="label">Max Contract Price</span><input name="max_contract_price" type="number" min="0" step="0.01" value="1.00"></label>
    <label class="panel"><span class="label">Max Open Positions</span><input name="max_open_positions" type="number" min="1" max="5" step="1" value="2"></label>
    <label class="panel"><span class="label">Adjusted Contract?</span><select name="is_adjusted"><option value="false">false</option><option value="true">true</option></select></label>
    <label class="panel"><span class="label">Earnings Window?</span><select name="earnings_window"><option value="false">false</option><option value="true">true</option></select></label>
    <label class="panel"><span class="label">Halted / LULD?</span><select name="halted"><option value="false">false</option><option value="true">true</option></select></label>
  </div>
  <p style="margin-top: 14px;"><button type="submit">Open Manual Trade Desk</button></p>
</form>
<h2>Use This Form Only After</h2>
{_list(result.get("before_use") or [])}
<h2>Hard Stops</h2>
{_list(result.get("hard_stops") or [])}
<h2>Next Pages</h2>
<table>
  <thead><tr><th>Page</th><th>URL</th></tr></thead>
  <tbody>
    <tr><td>Go-live rehearsal</td><td><a href="/ops/go-live-rehearsal?account_value=50&format=html">/ops/go-live-rehearsal?account_value=50&format=html</a></td></tr>
    <tr><td>Live review cycle</td><td><a href="/ops/live-review-cycle?account_value=50&format=html">/ops/live-review-cycle?account_value=50&format=html</a></td></tr>
    <tr><td>Session risk</td><td><a href="/risk/session?account_value=50&format=html">/risk/session?account_value=50&format=html</a></td></tr>
  </tbody>
</table>
"""
    return _html_page("Manual Snapshot Form", body, payload)


def _manual_broker_action_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    recheck = result.get("recheck_request") or {}
    recheck_payload = recheck.get("payload") or {}
    checkpoint = result.get("journal_checkpoint_request") or {}
    body = f"""
<div class="topbar">
  <div>
    <h1>Manual Broker Action Journal</h1>
    <p>User-reported broker action record, pending-buy recheck card, and checkpoint reminder. Review-only.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Ticker", result.get("ticker")),
    ("Contract", result.get("contract_symbol")),
    ("Action", result.get("action_type")),
    ("Order Status", result.get("order_status")),
    ("Side", result.get("side")),
    ("Direction", result.get("direction")),
    ("Limit Price", result.get("limit_price")),
    ("Quantity", result.get("quantity")),
    ("Submitted At", result.get("submitted_at")),
    ("MCP Broker Action", result.get("mcp_broker_action")),
])}
<h2>Pending Buy Recheck</h2>
{_field_grid([
    ("Pending Buy", result.get("pending_buy")),
    ("Recheck Seconds", result.get("pending_buy_recheck_seconds")),
    ("Recheck After", result.get("recheck_after")),
    ("Tool", recheck.get("tool")),
    ("Endpoint", recheck.get("endpoint")),
    ("Payload", recheck_payload),
])}
<h2>Checkpoint</h2>
{_field_grid([
    ("Endpoint", checkpoint.get("endpoint")),
    ("When", checkpoint.get("when")),
])}
<h2>Next Steps</h2>
{_list(result.get("next_steps") or [])}
"""
    return _html_page("Manual Broker Action Journal", body, payload)


def _pending_recheck_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    body = f"""
<div class="topbar">
  <div>
    <h1>Pending Buy Recheck</h1>
    <p>Review-only stale pending-buy check. This cannot leave, cancel, or replace any order.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Ticker", result.get("ticker")),
    ("Age Seconds", result.get("age_seconds")),
    ("Limit Price", result.get("limit_price")),
    ("Current Price", result.get("current_price")),
    ("Price Drift", result.get("price_drift_pct")),
    ("Recheck Window", result.get("pending_buy_recheck_seconds")),
    ("Can Cancel Orders", payload.get("can_cancel_order_from_this_mcp")),
])}
<h2>Reasons</h2>
{_list(result.get("reasons") or [])}
<h2>Warnings</h2>
{_list(result.get("warnings") or [])}
<h2>Next Action</h2>
{_list([result.get("next_action")] if result.get("next_action") else [])}
"""
    return _html_page("Pending Buy Recheck", body, payload)


def _paper_option_summary_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    open_rows = []
    for item in result.get("open_entries") or []:
        open_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('entry_event_id') or ''))}</td>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('contract_symbol') or ''))}</td>"
            f"<td>{escape(str(item.get('entry_price') or ''))}</td>"
            f"<td>{escape(str(item.get('quantity') or ''))}</td>"
            f"<td>{escape(str(item.get('timestamp') or ''))}</td>"
            "</tr>"
        )
    close_rows = []
    for item in result.get("recent_closes") or []:
        close_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('entry_event_id') or ''))}</td>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('contract_symbol') or ''))}</td>"
            f"<td>{escape(str(item.get('pnl_dollars') or ''))}</td>"
            f"<td>{escape(str(item.get('return_pct') or ''))}</td>"
            f"<td>{escape(str(item.get('classification') or ''))}</td>"
            f"<td>{escape(str(item.get('timestamp') or ''))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Paper Option Ledger</h1>
    <p>Manual/paper option entries, closes, P/L, and learning labels. No broker contact.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Entries", result.get("entry_count")),
    ("Open", result.get("open_count")),
    ("Closed", result.get("closed_count")),
    ("Win Rate", result.get("win_rate")),
    ("Total P/L", result.get("total_pnl_dollars")),
    ("Avg P/L", result.get("average_pnl_dollars")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Open Paper Entries</h2>
<table>
  <thead><tr><th>ID</th><th>Ticker</th><th>Contract</th><th>Entry</th><th>Qty</th><th>Logged</th></tr></thead>
  <tbody>{''.join(open_rows) if open_rows else '<tr><td colspan="6">No open paper option entries.</td></tr>'}</tbody>
</table>
<h2>Recent Closes</h2>
<table>
  <thead><tr><th>Entry ID</th><th>Ticker</th><th>Contract</th><th>P/L</th><th>Return</th><th>Learning</th><th>Closed</th></tr></thead>
  <tbody>{''.join(close_rows) if close_rows else '<tr><td colspan="7">No closed paper option trades yet.</td></tr>'}</tbody>
</table>
"""
    return _html_page("Paper Option Ledger", body, payload)


def _paper_option_position_watch_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    close_request = result.get("close_request") or {}
    body = f"""
<div class="topbar">
  <div>
    <h1>Option Position Watch</h1>
    <p>Review-only management card for an open manual/paper option. It cannot close or modify broker orders.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Ticker", result.get("ticker")),
    ("Direction", result.get("direction")),
    ("Contract", result.get("contract_symbol")),
    ("Entry", result.get("entry_price")),
    ("Current Mark", result.get("current_mark")),
    ("Return", result.get("return_pct")),
    ("P/L", result.get("pnl_dollars")),
    ("Spread", result.get("spread_pct")),
    ("Next Action", result.get("next_action")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Warnings</h2>
{_list(result.get("warnings") or [])}
<h2>Prepared Close Ledger Payload</h2>
{_field_grid([
    ("Endpoint", close_request.get("endpoint")),
    ("Entry ID", close_request.get("entry_id")),
    ("Contract", close_request.get("contract_symbol")),
    ("Exit Price", close_request.get("exit_price")),
    ("Exit Reason", close_request.get("exit_reason")),
])}
<h2>Management Rules</h2>
{_list(result.get("management_rules") or [])}
"""
    return _html_page("Option Position Watch", body, payload)


def _session_risk_guard_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    open_rows = []
    for item in result.get("open_entries") or []:
        open_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('entry_event_id') or ''))}</td>"
            f"<td>{escape(str(item.get('ticker') or ''))}</td>"
            f"<td>{escape(str(item.get('contract_symbol') or ''))}</td>"
            f"<td>{escape(str(item.get('direction') or ''))}</td>"
            f"<td>{escape(str(item.get('entry_debit_dollars') or ''))}</td>"
            "</tr>"
        )
    link_rows = []
    for label, url in (result.get("action_links") or {}).items():
        link_rows.append(
            "<tr>"
            f"<td>{escape(str(label).replace('_', ' ').title())}</td>"
            f"<td><a href=\"{escape(str(url))}\">{escape(str(url))}</a></td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Session Risk Guard</h1>
    <p>Journal-based risk view for open manual/paper option exposure. Review-only; broker balances are not verified.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Account Ref.", result.get("account_value_reference")),
    ("Per-Trade Cap", result.get("per_trade_cap_dollars")),
    ("Today", result.get("trading_day")),
    ("Paper Daily Losses", result.get("paper_daily_loss_count")),
    ("Paper Daily Closed Trades", result.get("paper_daily_closed_trade_count")),
    ("Paper Daily Closed P/L", result.get("paper_daily_closed_pnl_dollars")),
    ("Real-Cash Daily Losses", f"{result.get('real_cash_daily_loss_count')} / {result.get('real_cash_daily_loss_lockout_count')}"),
    ("Real-Cash Daily Closed P/L", result.get("real_cash_daily_closed_pnl_dollars")),
    ("Real-Cash Open Positions", f"{result.get('real_cash_open_position_count')} / {result.get('max_open_positions')}"),
    ("Paper Open Positions", result.get("paper_open_position_count")),
    ("Next Action", result.get("next_action")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Blocking Reasons</h2>
{_list(result.get("blocking_reasons") or [])}
<h2>Warnings</h2>
{_list(result.get("warnings") or [])}
<h2>Open Entries</h2>
<table>
  <thead><tr><th>ID</th><th>Ticker</th><th>Contract</th><th>Direction</th><th>Open Risk</th></tr></thead>
  <tbody>{''.join(open_rows) if open_rows else '<tr><td colspan="5">No open journaled option entries.</td></tr>'}</tbody>
</table>
<h2>Action Links</h2>
<table>
  <thead><tr><th>Action</th><th>Link</th></tr></thead>
  <tbody>{''.join(link_rows)}</tbody>
</table>
<h2>Rules</h2>
{_list(result.get("rules") or [])}
"""
    return _html_page("Session Risk Guard", body, payload)


def _health_full_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    safety = result.get("safety") or {}
    options_data = result.get("options_data_status") or {}
    truth = result.get("truth_source_status") or {}
    cash_readiness = truth.get("cash_readiness") or {}
    schemas = result.get("schema_versions") or {}
    required_tools = result.get("required_tools") or {}
    missing_tools = [name for name, exposed in required_tools.items() if not exposed]
    readable_status = result.get("status") or "UNKNOWN"
    body = f"""
<div class="topbar">
  <div>
    <h1>Full Health</h1>
    <p>Readable deployment, safety, tool, and truth-source check. This page does not run a scan or contact a broker.</p>
  </div>
  <div><span class="badge {_status_class(readable_status)}">{escape(str(readable_status))}</span></div>
</div>
{_field_grid([
    ("Build", result.get("build_version")),
    ("Expected Build", result.get("expected_build_version")),
    ("Build Match", result.get("build_matches_expected")),
    ("Tool Count", result.get("tool_count")),
    ("Missing Required Tools", len(missing_tools)),
    ("Review Only", safety.get("review_only")),
    ("Can Place Orders", safety.get("can_place_order_from_this_mcp")),
    ("Can Cancel Orders", safety.get("can_cancel_order_from_this_mcp")),
    ("Market Orders Allowed", safety.get("market_orders_allowed")),
])}
<h2>Options Truth</h2>
{_field_grid([
    ("Options Provider", options_data.get("configured_provider")),
    ("Realtime Required", options_data.get("options_realtime_required")),
    ("Realtime Available", options_data.get("automated_realtime_options_available")),
    ("Real-Money Truth", options_data.get("real_money_options_truth_status")),
    ("Broker Snapshot Required", options_data.get("broker_snapshot_required")),
    ("Cash Ready", cash_readiness.get("cash_ready")),
    ("Reason", cash_readiness.get("reason")),
])}
<h2>Schema Versions</h2>
{_field_grid([(str(key), value) for key, value in schemas.items()])}
<h2>Missing Required Tools</h2>
{_list(missing_tools)}
<h2>Next Steps</h2>
{_list(result.get("next_steps") or [])}
"""
    return _html_page("Full Health", body, payload)


def _journal_checkpoint_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    count_rows = []
    for event_type, count in sorted((result.get("event_type_counts") or {}).items()):
        count_rows.append(
            "<tr>"
            f"<td>{escape(str(event_type))}</td>"
            f"<td>{escape(str(count))}</td>"
            "</tr>"
        )
    recent_rows = []
    for event in (result.get("events") or [])[:25]:
        recent_rows.append(
            "<tr>"
            f"<td>{escape(str(event.get('id') or ''))}</td>"
            f"<td>{escape(str(event.get('timestamp') or ''))}</td>"
            f"<td>{escape(str(event.get('event_type') or ''))}</td>"
            f"<td>{escape(str((event.get('payload') or {}).get('status') or ''))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Journal Checkpoint</h1>
    <p>Export recent review, paper, outcome, and learning events before Render restarts or redeploys.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Events", result.get("event_count")),
    ("Latest Event ID", result.get("latest_event_id")),
    ("Checkpoint Event ID", result.get("checkpoint_event_id")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Event Type Counts</h2>
<table>
  <thead><tr><th>Event Type</th><th>Count</th></tr></thead>
  <tbody>{''.join(count_rows) if count_rows else '<tr><td colspan="2">No events exported.</td></tr>'}</tbody>
</table>
<h2>Recent Events</h2>
<table>
  <thead><tr><th>ID</th><th>Time</th><th>Type</th><th>Status</th></tr></thead>
  <tbody>{''.join(recent_rows) if recent_rows else '<tr><td colspan="4">No events exported.</td></tr>'}</tbody>
</table>
<h2>Restore Guidance</h2>
{_list(result.get("restore_guidance") or [])}
"""
    return _html_page("Journal Checkpoint", body, payload)


def _journal_checkpoint_restore_html(payload: dict[str, Any]) -> HTMLResponse:
    result = payload.get("result") or {}
    count_rows = []
    for event_type, count in sorted((result.get("restored_event_type_counts") or {}).items()):
        count_rows.append(
            "<tr>"
            f"<td>{escape(str(event_type))}</td>"
            f"<td>{escape(str(count))}</td>"
            "</tr>"
        )
    restored_rows = []
    for item in (result.get("restored_events") or [])[:25]:
        restored_rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('event_type') or ''))}</td>"
            f"<td>{escape(str(item.get('original_id') or ''))}</td>"
            f"<td>{escape(str(item.get('id') or ''))}</td>"
            "</tr>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>Journal Checkpoint Restore</h1>
    <p>Restore saved local journal evidence after a Render restart. Review-only; no broker access.</p>
  </div>
  <div><span class="badge {_status_class(result.get('status'))}">{escape(str(result.get('status') or 'UNKNOWN'))}</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Source", result.get("source_label")),
    ("Checkpoint Build", result.get("checkpoint_build_version")),
    ("Requested Events", result.get("requested_event_count")),
    ("Restored Events", result.get("restored_count")),
    ("Skipped Duplicates", result.get("skipped_duplicate_count")),
    ("Invalid Events", result.get("invalid_count")),
    ("Restore Event ID", result.get("restore_event_id")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
])}
<h2>Restored Event Type Counts</h2>
<table>
  <thead><tr><th>Event Type</th><th>Count</th></tr></thead>
  <tbody>{''.join(count_rows) if count_rows else '<tr><td colspan="2">No event types restored.</td></tr>'}</tbody>
</table>
<h2>Restored Events</h2>
<table>
  <thead><tr><th>Type</th><th>Original ID</th><th>New ID</th></tr></thead>
  <tbody>{''.join(restored_rows) if restored_rows else '<tr><td colspan="3">No new events restored.</td></tr>'}</tbody>
</table>
<h2>Notes</h2>
{_list(result.get("notes") or [])}
"""
    return _html_page("Journal Checkpoint Restore", body, payload)


def _blueprint_html(payload: dict[str, Any], title: str) -> HTMLResponse:
    result = payload.get("result") or {}
    sections = []
    if result.get("primary_edges"):
        rows = []
        for edge in result.get("primary_edges") or []:
            rows.append(
                "<tr>"
                f"<td>{escape(str(edge.get('edge') or ''))}</td>"
                f"<td>{escape(str(edge.get('proxy') or ''))}</td>"
                f"<td>{escape(str(edge.get('horizon') or ''))}</td>"
                f"<td>{escape(str(edge.get('evidence') or ''))}</td>"
                f"<td>{escape(str(edge.get('implementation_priority') or ''))}</td>"
                "</tr>"
            )
        sections.append(
            "<h2>Primary Edges</h2>"
            "<table><thead><tr><th>Edge</th><th>Measurable Proxy</th><th>Horizon</th><th>Evidence</th><th>Priority</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    if result.get("positive_modules"):
        rows = []
        for module in result.get("positive_modules") or []:
            rows.append(
                "<tr>"
                f"<td>{escape(str(module.get('name') or ''))}</td>"
                f"<td>{escape(str(module.get('max_points') or ''))}</td>"
                f"<td>{escape(', '.join(str(item) for item in module.get('features', [])))}</td>"
                f"<td>{escape(str(module.get('current_data_status') or ''))}</td>"
                "</tr>"
            )
        sections.append(
            "<h2>Positive Modules</h2>"
            "<table><thead><tr><th>Module</th><th>Max</th><th>Features</th><th>Data Status</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    if result.get("false_positive_penalties"):
        rows = []
        for penalty in result.get("false_positive_penalties") or []:
            rows.append(
                "<tr>"
                f"<td>{escape(str(penalty.get('name') or ''))}</td>"
                f"<td>{escape(str(penalty.get('max_penalty') or ''))}</td>"
                "</tr>"
            )
        sections.append(
            "<h2>False-Positive Penalties</h2>"
            "<table><thead><tr><th>Penalty</th><th>Max</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    if result.get("action_bands"):
        rows = []
        for band in result.get("action_bands") or []:
            rows.append(
                "<tr>"
                f"<td>{escape(str(band.get('band') or ''))}</td>"
                f"<td>{escape(str(band.get('score') or ''))}</td>"
                f"<td>{escape(str(band.get('meaning') or ''))}</td>"
                "</tr>"
            )
        sections.append(
            "<h2>Action Bands</h2>"
            "<table><thead><tr><th>Band</th><th>Score</th><th>Meaning</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    body = f"""
<div class="topbar">
  <div>
    <h1>{escape(title)}</h1>
    <p>{escape(str(result.get('mission') or result.get('model') or 'Research-backed scoring map for the Trading Monster.'))}</p>
  </div>
  <div><span class="badge ok">REVIEW ONLY</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
    ("Do Not Auto Apply Learning", (result.get("safety") or {}).get("do_not_auto_apply_learning", True)),
])}
{''.join(sections) if sections else '<p>No table sections returned.</p>'}
"""
    return _html_page(title, body, payload)


async def fallback_safety(request: Request) -> JSONResponse:
    del request
    settings = container.settings
    return JSONResponse(
        _review_only_envelope(
            {
                "place_orders": False,
                "market_orders_allowed": False,
                "manual_approval_required": settings.manual_approval_required,
                "approval_phrase": settings.approval_phrase,
                "automation_flags_inert": True,
                "pending_buy_recheck_seconds": settings.pending_buy_recheck_seconds,
            }
        )
    )


async def fallback_release_manifest(request: Request) -> JSONResponse:
    del request
    return JSONResponse(_release_manifest_payload())


async def fallback_market_scan(request: Request) -> JSONResponse:
    params = request.query_params
    mode = params.get("mode") or "conservative_review_only"
    max_candidates = _int_or_default(params.get("max_candidates"), 25)
    result = container.scanner.run_market_scan(mode, _tickers(params.get("tickers")), max_candidates)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_scalp_scan(request: Request) -> JSONResponse:
    params = request.query_params
    max_candidates = _int_or_default(params.get("max_candidates"), 25)
    result = container.scanner.run_market_scan("scalp_review", _tickers(params.get("tickers")), max_candidates)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_market_readiness(request: Request) -> JSONResponse:
    params = request.query_params
    max_candidates = _int_or_default(params.get("max_candidates"), 25)
    result = _market_readiness_check(container, _tickers(params.get("tickers")), max_candidates)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_review_harvest(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _run_review_harvest(
        container,
        _tickers(params.get("tickers")),
        params.get("mode") or "scalp_review",
        _int_or_default(params.get("max_candidates"), 25),
        _int_or_default(params.get("review_top_n"), 8),
        _float_or_none(params.get("max_contract_price")),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _review_harvest_html(payload)
    return JSONResponse(payload)


async def fallback_session_playbook(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _get_market_session_playbook(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _session_playbook_html(payload)
    return JSONResponse(payload)


async def fallback_event_volatility_playbook(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _get_event_volatility_playbook(
        container,
        params.get("event_name") or "spacex_ipo",
        _float_or_none(params.get("account_value")) or 50.0,
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _event_volatility_playbook_html(payload)
    return JSONResponse(payload)


async def fallback_event_radar(request: Request) -> JSONResponse | HTMLResponse:
    result = _get_event_radar(container)
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _event_radar_html(payload)
    return JSONResponse(payload)


async def fallback_event_volatility_scan(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _run_event_volatility_scan(
        container,
        params.get("event_name") or "spacex_ipo",
        _tickers(params.get("tickers")),
        _int_or_default(params.get("max_candidates"), 25),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("review_top_n"), 8),
        _float_or_none(params.get("max_contract_price")),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _event_volatility_scan_html(payload)
    return JSONResponse(payload)


async def fallback_broad_opportunity_scan(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    include_event_raw = (params.get("include_event_context") or "true").strip().lower()
    result = _run_broad_opportunity_scan(
        container,
        _tickers(params.get("tickers")),
        _int_or_default(params.get("max_candidates"), 25),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("review_top_n"), 10),
        _float_or_none(params.get("max_contract_price")),
        include_event_raw not in {"false", "0", "no"},
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _broad_opportunity_scan_html(payload)
    return JSONResponse(payload)


async def fallback_data_truth_cockpit(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _get_data_truth_cockpit(
        container,
        _tickers(params.get("tickers")),
        _int_or_default(params.get("max_tickers"), 12),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _data_truth_cockpit_html(payload)
    return JSONResponse(payload)


async def fallback_system_communication_audit(request: Request) -> JSONResponse | HTMLResponse:
    result = _get_system_communication_audit(container)
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _system_communication_audit_html(payload)
    return JSONResponse(payload)


async def fallback_harvest_followup(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    classify_raw = (params.get("classify") or "true").strip().lower()
    result = _run_latest_harvest_followup(
        container,
        _int_or_default(params.get("limit"), 5),
        classify_raw not in {"false", "0", "no"},
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _harvest_followup_html(payload)
    return JSONResponse(payload)


async def fallback_command_center(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _get_ops_command_center(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _command_center_html(payload)
    return JSONResponse(payload)


async def fallback_trading_day_launch(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _get_trading_day_launch_checklist(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("max_candidates"), 25),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _trading_day_launch_html(payload)
    return JSONResponse(payload)


async def fallback_tomorrow_operator_brief(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _get_tomorrow_operator_brief(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("max_candidates"), 25),
    )
    payload = _review_only_envelope({"result": result})
    if request.url.path == "/" or _wants_html(request):
        return _tomorrow_operator_brief_html(payload)
    return JSONResponse(payload)


async def fallback_go_live_rehearsal(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _run_go_live_rehearsal(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("max_candidates"), 25),
        _truthy(params.get("include_market_check")),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _go_live_rehearsal_html(payload)
    return JSONResponse(payload)


async def fallback_trading_day_heartbeat(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _run_trading_day_heartbeat(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("max_candidates"), 25),
        _int_or_default(params.get("review_top_n"), 8),
        _float_or_none(params.get("max_contract_price")),
        params.get("force_phase"),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _trading_day_heartbeat_html(payload, auto_refresh=_truthy(params.get("auto_refresh")))
    return JSONResponse(payload)


async def fallback_day_monitor(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _run_trading_day_heartbeat(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("max_candidates"), 25),
        _int_or_default(params.get("review_top_n"), 8),
        _float_or_none(params.get("max_contract_price")),
        params.get("force_phase"),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _trading_day_heartbeat_html(payload, auto_refresh=not _truthy(params.get("no_refresh")))
    return JSONResponse(payload)


async def fallback_day_alerts(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _summarize_trading_day_alerts(container, _int_or_default(params.get("limit"), 50))
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _trading_day_alerts_html(payload)
    return JSONResponse(payload)


async def fallback_morning_autopilot(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _run_morning_readiness_autopilot(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("max_candidates"), 25),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _morning_autopilot_html(payload)
    return JSONResponse(payload)


async def fallback_autonomous_morning_scan(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _run_autonomous_morning_scan(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("max_candidates"), 25),
        _int_or_default(params.get("review_top_n"), 8),
        _float_or_none(params.get("max_contract_price")),
        params.get("force_phase"),
        _int_or_default(params.get("catalyst_top_n"), 5),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _autonomous_morning_scan_html(payload, auto_refresh=not _truthy(params.get("no_refresh")))
    return JSONResponse(payload)


async def fallback_live_review_cycle(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    include_followup = (params.get("include_followup") or "false").strip().lower() in {"1", "true", "yes"}
    result = _run_live_review_cycle(
        container,
        _tickers(params.get("tickers")),
        _float_or_none(params.get("account_value")) or 50.0,
        _int_or_default(params.get("max_candidates"), 25),
        _int_or_default(params.get("review_top_n"), 8),
        _float_or_none(params.get("max_contract_price")),
        include_followup,
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _live_review_cycle_html(payload)
    return JSONResponse(payload)


async def fallback_market_open_observer(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _run_market_open_observer(
        container,
        _tickers(params.get("tickers")),
        _int_or_default(params.get("max_candidates"), 25),
        _int_or_default(params.get("cadence_minutes"), 5),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _market_open_observer_html(payload)
    return JSONResponse(payload)


async def fallback_observer_followup(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    include_passes = (params.get("include_passes") or "true").strip().lower() not in {"0", "false", "no"}
    classify = (params.get("classify") or "true").strip().lower() not in {"0", "false", "no"}
    result = _run_observer_followup(
        container,
        _int_or_default(params.get("limit_observations"), 3),
        _int_or_default(params.get("max_items"), 20),
        include_passes,
        classify,
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _observer_followup_html(payload)
    return JSONResponse(payload)


async def fallback_manual_preflight(request: Request) -> JSONResponse | HTMLResponse:
    if request.method == "POST":
        body = await request.json()
    else:
        params = request.query_params
        body = {
            "ticker": params.get("ticker"),
            "underlying": params.get("underlying"),
            "contract_symbol": params.get("contract_symbol"),
            "direction": params.get("direction"),
            "bid": _float_or_none(params.get("bid")),
            "ask": _float_or_none(params.get("ask")),
            "volume": _int_or_default(params.get("volume"), 0),
            "open_interest": _int_or_default(params.get("open_interest"), 0),
            "dte": _int_or_default(params.get("dte"), 0),
            "strike": _float_or_none(params.get("strike")),
            "expiration": params.get("expiration"),
        }
    snapshot = body.get("snapshot") if isinstance(body.get("snapshot"), dict) else body
    result = _build_manual_trade_preflight_ticket(
        container,
        snapshot,
        _float_or_none(str(body.get("account_value"))) if body.get("account_value") is not None else 50.0,
        _float_or_none(str(body.get("max_contract_price"))) if body.get("max_contract_price") is not None else None,
        str(body.get("notes") or ""),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _manual_preflight_html(payload)
    return JSONResponse(payload)


async def fallback_manual_trade_desk(request: Request) -> JSONResponse | HTMLResponse:
    if request.method == "POST":
        body = await request.json()
    else:
        params = request.query_params
        body = {
            "ticker": params.get("ticker"),
            "underlying": params.get("underlying"),
            "underlying_price": _float_or_none(params.get("underlying_price")),
            "contract_symbol": params.get("contract_symbol"),
            "expected_contract_symbol": params.get("expected_contract_symbol"),
            "displayed_symbol": params.get("displayed_symbol"),
            "direction": params.get("direction"),
            "bid": _float_or_none(params.get("bid")),
            "ask": _float_or_none(params.get("ask")),
            "bid_size": _int_or_default(params.get("bid_size"), 0),
            "ask_size": _int_or_default(params.get("ask_size"), 0),
            "volume": _int_or_default(params.get("volume"), 0),
            "open_interest": _int_or_default(params.get("open_interest"), 0),
            "dte": _int_or_default(params.get("dte"), 0),
            "strike": _float_or_none(params.get("strike")),
            "expiration": params.get("expiration"),
            "broker_snapshot_ts": params.get("broker_snapshot_ts"),
            "option_quote_ts": params.get("option_quote_ts") or params.get("quote_ts"),
            "source": params.get("source") or "manual_broker_snapshot",
            "multiplier": _int_or_default(params.get("multiplier"), 100),
            "deliverable": params.get("deliverable"),
            "is_adjusted": _truthy(params.get("is_adjusted")),
            "earnings_window": _truthy(params.get("earnings_window")),
            "ex_div_window": _truthy(params.get("ex_div_window")),
            "halted": _truthy(params.get("halted")),
            "luld": _truthy(params.get("luld")),
            "expiration_day": _truthy(params.get("expiration_day")),
            "zero_dte": _truthy(params.get("zero_dte")),
            "account_value": _float_or_none(params.get("account_value")),
            "max_contract_price": _float_or_none(params.get("max_contract_price")),
            "max_open_positions": _int_or_default(params.get("max_open_positions"), 2),
            "notes": params.get("notes"),
        }
    snapshot = body.get("snapshot") if isinstance(body.get("snapshot"), dict) else body
    result = _build_manual_trade_desk(
        container,
        snapshot,
        _float_or_none(str(body.get("account_value"))) if body.get("account_value") is not None else 50.0,
        _float_or_none(str(body.get("max_contract_price"))) if body.get("max_contract_price") is not None else None,
        str(body.get("notes") or ""),
        _int_or_default(str(body.get("max_open_positions")), 2) if body.get("max_open_positions") is not None else 2,
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _manual_trade_desk_html(payload)
    return JSONResponse(payload)


async def fallback_manual_snapshot_form(request: Request) -> JSONResponse | HTMLResponse:
    payload = _review_only_envelope(
        {
            "result": {
                "status": "MANUAL_SNAPSHOT_FORM_READY",
                "build_version": BUILD_VERSION,
                "destination": "/trade/manual-desk",
                "before_use": [
                    "A live review cycle produced a candidate worth broker-side inspection.",
                    "You are copying fields from the actual broker contract screen.",
                    "The contract symbol, bid, ask, volume, open interest, DTE, and strike are visible.",
                    "Session risk is not blocked.",
                ],
                "hard_stops": [
                    "Do not use market orders.",
                    "Do not enter a broker action from this form.",
                    "Do not continue if the broker contract differs from the reviewed contract.",
                    "Do not continue if spread, liquidity, or direction worsened since review.",
                ],
                "review_only": True,
                "can_place_order_from_this_mcp": False,
                "can_cancel_order_from_this_mcp": False,
            }
        }
    )
    if _wants_html(request):
        return _manual_snapshot_form_html(payload)
    return JSONResponse(payload)


async def fallback_manual_broker_action(request: Request) -> JSONResponse | HTMLResponse:
    if request.method == "POST":
        body = await request.json()
    else:
        params = request.query_params
        body = {
            "ticker": params.get("ticker"),
            "contract_symbol": params.get("contract_symbol"),
            "action_type": params.get("action_type"),
            "order_status": params.get("order_status"),
            "side": params.get("side"),
            "direction": params.get("direction"),
            "limit_price": _float_or_none(params.get("limit_price")),
            "reviewed_price": _float_or_none(params.get("reviewed_price") or params.get("reviewed_ask")),
            "fill_price": _float_or_none(params.get("fill_price") or params.get("execution_price")),
            "quantity": _int_or_default(params.get("quantity"), 1),
            "submitted_at": params.get("submitted_at"),
            "broker_snapshot_ts": params.get("broker_snapshot_ts") or params.get("snapshot_ts"),
            "execution_ts": params.get("execution_ts") or params.get("filled_at"),
            "expected_contract_symbol": params.get("expected_contract_symbol"),
            "screenshot_hash": params.get("screenshot_hash") or params.get("proof_hash"),
            "operator_id": params.get("operator_id"),
            "is_options_order": (params.get("is_options_order") or "").strip().lower() in {"1", "true", "yes"},
            "mode": params.get("mode"),
            "notes": params.get("notes"),
        }
    result = _log_manual_broker_action(container, body)
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _manual_broker_action_html(payload)
    return JSONResponse(payload)


async def fallback_pending_recheck(request: Request) -> JSONResponse | HTMLResponse:
    if request.method == "POST":
        body = await request.json()
    else:
        params = request.query_params
        body = {
            "ticker": params.get("ticker"),
            "submitted_at": params.get("submitted_at"),
            "limit_price": _float_or_none(params.get("limit_price")),
            "is_options_order": (params.get("is_options_order") or "").strip().lower() in {"1", "true", "yes"},
            "direction": params.get("direction") or "call",
            "mode": params.get("mode") or "scalp_review",
        }
    result = container.pending_orders.review_pending_buy(
        str(body.get("ticker") or ""),
        str(body.get("submitted_at") or ""),
        _float_or_none(str(body.get("limit_price"))) if body.get("limit_price") is not None else None,
        bool(body.get("is_options_order")),
        str(body.get("direction") or "call"),
        str(body.get("mode") or "scalp_review"),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _pending_recheck_html(payload)
    return JSONResponse(payload)


async def fallback_paper_option_entry(request: Request) -> JSONResponse:
    body = await request.json()
    ticket = body.get("ticket") if isinstance(body.get("ticket"), dict) else body.get("source_preflight")
    if not isinstance(ticket, dict):
        ticket = {}
    result = _log_manual_option_paper_entry(
        container,
        ticket,
        _float_or_none(str(body.get("fill_price"))) if body.get("fill_price") is not None else 0.0,
        _int_or_default(str(body.get("quantity")) if body.get("quantity") is not None else None, 1),
        _float_or_none(str(body.get("underlying_price"))) if body.get("underlying_price") is not None else None,
        str(body.get("notes") or ""),
    )
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_paper_option_close(request: Request) -> JSONResponse:
    body = await request.json()
    entry_id_raw = body.get("entry_id")
    entry_id = _int_or_default(str(entry_id_raw), 0) if entry_id_raw is not None else None
    result = _close_manual_option_paper_trade(
        container,
        entry_id if entry_id else None,
        str(body.get("contract_symbol") or "") or None,
        _float_or_none(str(body.get("exit_price"))) if body.get("exit_price") is not None else 0.0,
        str(body.get("exit_reason") or "manual_close"),
        str(body.get("notes") or ""),
    )
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_paper_option_watch(request: Request) -> JSONResponse | HTMLResponse:
    if request.method == "POST":
        body = await request.json()
        entry_id_raw = body.get("entry_id")
        entry_id = _int_or_default(str(entry_id_raw), 0) if entry_id_raw is not None else None
        result = _watch_manual_option_position(
            container,
            entry_id if entry_id else None,
            str(body.get("contract_symbol") or "") or None,
            _float_or_none(str(body.get("current_bid"))) if body.get("current_bid") is not None else None,
            _float_or_none(str(body.get("current_ask"))) if body.get("current_ask") is not None else None,
            _float_or_none(str(body.get("current_mark"))) if body.get("current_mark") is not None else None,
            _float_or_none(str(body.get("underlying_price"))) if body.get("underlying_price") is not None else None,
            _float_or_none(str(body.get("underlying_vwap"))) if body.get("underlying_vwap") is not None else None,
            str(body.get("notes") or ""),
        )
    else:
        params = request.query_params
        entry_id_raw = params.get("entry_id")
        entry_id = _int_or_default(entry_id_raw, 0) if entry_id_raw is not None else None
        result = _watch_manual_option_position(
            container,
            entry_id if entry_id else None,
            params.get("contract_symbol") or None,
            _float_or_none(params.get("current_bid")),
            _float_or_none(params.get("current_ask")),
            _float_or_none(params.get("current_mark")),
            _float_or_none(params.get("underlying_price")),
            _float_or_none(params.get("underlying_vwap")),
            params.get("notes") or "",
        )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _paper_option_position_watch_html(payload)
    return JSONResponse(payload)


async def fallback_paper_option_summary(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _summarize_manual_option_paper_trades(container, _int_or_default(params.get("limit"), 100))
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _paper_option_summary_html(payload)
    return JSONResponse(payload)


async def fallback_session_risk_guard(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = _get_session_risk_guard(
        container,
        _float_or_none(params.get("account_value")) or 50.0,
        _float_or_none(params.get("proposed_risk_dollars")),
        _int_or_default(params.get("max_open_positions"), 2),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _session_risk_guard_html(payload)
    return JSONResponse(payload)


async def fallback_failure_mode_audit(request: Request) -> JSONResponse | HTMLResponse:
    result = _get_failure_mode_audit(container)
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _failure_mode_audit_html(payload)
    return JSONResponse(payload)


async def fallback_journal_checkpoint(request: Request) -> JSONResponse | HTMLResponse:
    if request.method == "POST":
        body = await request.json()
        restore_source = body.get("source_label") or body.get("restore_source") or "manual_restore"
        checkpoint = body.get("checkpoint") if isinstance(body.get("checkpoint"), dict) else body
        if isinstance(checkpoint, dict) and isinstance(checkpoint.get("events"), list):
            result = _restore_journal_checkpoint(
                container,
                checkpoint,
                str(restore_source),
                _int_or_default(str(body.get("max_events")) if body.get("max_events") is not None else None, 500),
            )
            payload = _review_only_envelope({"result": result})
            if _wants_html(request):
                return _journal_checkpoint_restore_html(payload)
            return JSONResponse(payload)
        limit = _int_or_default(str(body.get("limit")) if body.get("limit") is not None else None, 500)
        event_types_raw = body.get("event_types")
        event_types = event_types_raw if isinstance(event_types_raw, list) else None
    else:
        params = request.query_params
        limit = _int_or_default(params.get("limit"), 500)
        event_types = [item.strip() for item in str(params.get("event_types") or "").split(",") if item.strip()] or None
    result = _export_journal_checkpoint(container, limit, event_types)
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _journal_checkpoint_html(payload)
    return JSONResponse(payload)


async def fallback_options_review(request: Request) -> JSONResponse:
    params = request.query_params
    ticker = (params.get("ticker") or "").strip().upper()
    if not ticker:
        return JSONResponse(_review_only_envelope({"error": "ticker is required"}), status_code=400)
    direction = params.get("direction") or "call"
    mode = params.get("mode") or "scalp_review"
    max_contract_price = _float_or_none(params.get("max_contract_price"))
    result = _review_candidate_for_options(container, ticker, direction, mode, max_contract_price)
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _options_review_html(payload)
    return JSONResponse(payload)


async def fallback_validate_broker_snapshot(request: Request) -> JSONResponse:
    payload = await request.json()
    max_contract_price = _float_or_none(str(payload.get("max_contract_price"))) if payload.get("max_contract_price") is not None else None
    snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else payload
    result = container.options.validate_broker_snapshot(snapshot, max_contract_price)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_options_data_status(request: Request) -> JSONResponse:
    result = container.options.options_data_status()
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_truth_source_status(request: Request) -> JSONResponse:
    del request
    result = container.market_truth.truth_source_status()
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_market_data_health(request: Request) -> JSONResponse:
    params = request.query_params
    result = container.market_truth.check_market_data_health(
        _tickers(params.get("tickers")),
        _int_or_default(params.get("max_tickers"), 10),
    )
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_catalyst_context(request: Request) -> JSONResponse:
    params = request.query_params
    ticker = (params.get("ticker") or "").strip().upper()
    if not ticker:
        return JSONResponse(_review_only_envelope({"error": "ticker is required"}), status_code=400)
    result = container.market_truth.get_catalyst_context(
        ticker,
        _int_or_default(params.get("lookback_days"), 3),
        _int_or_default(params.get("lookahead_days"), 7),
    )
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_log_review_decision(request: Request) -> JSONResponse:
    payload = await request.json()
    result = container.review_outcomes.log_review_decision(payload)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_check_review_outcome(request: Request) -> JSONResponse:
    if request.method == "GET":
        params = request.query_params
        payload: dict[str, Any] = {
            "review_id": params.get("review_id"),
            "ticker": params.get("ticker"),
            "direction": params.get("direction"),
            "entry_reference": _float_or_none(params.get("entry_reference")),
            "review_timestamp": params.get("review_timestamp"),
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        horizons = None
    else:
        body = await request.json()
        payload = body.get("review") if isinstance(body.get("review"), dict) else body
        horizons = body.get("horizons") if isinstance(body.get("horizons"), dict) else None
    result = container.review_outcomes.check_review_outcome(payload, horizons)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_learning_classify(request: Request) -> JSONResponse:
    body = await request.json()
    snapshot = body.get("snapshot") if isinstance(body.get("snapshot"), dict) else {}
    outcome = body.get("outcome") if isinstance(body.get("outcome"), dict) else {}
    help_threshold = _float_or_none(str(body.get("help_threshold"))) if body.get("help_threshold") is not None else 0.003
    missed_move_threshold = _float_or_none(str(body.get("missed_move_threshold"))) if body.get("missed_move_threshold") is not None else 0.006
    result = container.learning.classify_review_outcome(snapshot, outcome, help_threshold or 0.003, missed_move_threshold or 0.006)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_learning_proposals(request: Request) -> JSONResponse:
    body = await request.json()
    classifications = body.get("classifications") if isinstance(body.get("classifications"), list) else None
    min_samples = _int_or_default(str(body.get("min_samples")) if body.get("min_samples") is not None else None, 3)
    limit = _int_or_default(str(body.get("limit")) if body.get("limit") is not None else None, 100)
    result = container.learning.generate_rule_proposals(classifications, min_samples, limit)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_setup_memory(request: Request) -> JSONResponse:
    body = await request.json()
    snapshot = body.get("snapshot") if isinstance(body, dict) else None
    if not isinstance(snapshot, dict):
        return JSONResponse(
            _review_only_envelope({"result": {"status": "SETUP_MEMORY_UNAVAILABLE", "reason": "snapshot object is required."}}),
            status_code=400,
        )
    limit = _int_or_default(str(body.get("limit")) if body.get("limit") is not None else None, 100)
    result = container.setup_memory.compare_snapshot(snapshot, limit)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_learning_dashboard(request: Request) -> JSONResponse | HTMLResponse:
    limit = _int_or_default(request.query_params.get("limit"), 50)
    classification_events = container.events.recent("learning_outcome_classification", limit)
    proposal_events = container.events.recent("learning_rule_proposals", 10)
    classifications = [event["payload"] for event in classification_events if isinstance(event.get("payload"), dict)]
    proposals = [event["payload"] for event in proposal_events if isinstance(event.get("payload"), dict)]
    counts = Counter(str(item.get("classification")) for item in classifications if item.get("classification"))
    payload = _review_only_envelope(
        {
            "classification_counts": dict(counts),
            "recent_classifications": classifications,
            "recent_rule_proposals": proposals,
            "notes": "Research memory only. Proposals must be backtested and manually approved before rules change.",
        }
    )
    if _wants_html(request):
        return _learning_dashboard_html(payload)
    return JSONResponse(payload)


async def fallback_offhours_plan(request: Request) -> JSONResponse | HTMLResponse:
    result = container.global_research.offhours_plan()
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        body = f"""
<div class="topbar">
  <div>
    <h1>Off-Hours Research Plan</h1>
    <p>Research lanes to keep learning while U.S. options liquidity is stale or closed.</p>
  </div>
  <div><span class="badge ok">RESEARCH ONLY</span></div>
</div>
{_field_grid([
    ("Build", payload.get("build_version")),
    ("Status", result.get("status")),
    ("Can Place Orders", payload.get("can_place_order_from_this_mcp")),
    ("Can Cancel Orders", payload.get("can_cancel_order_from_this_mcp")),
])}
<h2>Use Cases</h2>
{_list(result.get("use_cases") or [])}
<h2>Recommended Now</h2>
{_list(result.get("recommended_now") or [])}
"""
        return _html_page("Off-Hours Research Plan", body, payload)
    return JSONResponse(payload)


async def fallback_global_research_scan(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    result = container.global_research.run_global_research_scan(
        market=params.get("market") or "global",
        symbols=_tickers(params.get("symbols")),
        period=params.get("period") or "5d",
        interval=params.get("interval") or "5m",
        max_candidates=_int_or_default(params.get("max_candidates"), 20),
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _global_scan_html(payload)
    return JSONResponse(payload)


async def fallback_crypto_rules(request: Request) -> JSONResponse:
    del request
    rules = container.crypto_paper.rules()
    return JSONResponse(
        _review_only_envelope(
            {
                "mode": "crypto_paper_only",
                "rules": rules.__dict__,
                "notes": "Paper-only crypto rules. No broker execution.",
            }
        )
    )


async def fallback_crypto_backtest(request: Request) -> JSONResponse | HTMLResponse:
    params = request.query_params
    overrides: dict[str, Any] = {}
    profile = params.get("profile")
    if profile:
        overrides["profile"] = profile
    excluded = _tickers(params.get("exclude_symbols"))
    if excluded:
        overrides["exclude_symbols"] = excluded
    result = container.crypto_paper.run_backtest(
        symbols=_tickers(params.get("symbols")),
        period=params.get("period") or "1d",
        interval=params.get("interval") or "5m",
        starting_cash=_float_or_none(params.get("starting_cash")) or 5.0,
        max_trades_per_symbol=_int_or_default(params.get("max_trades_per_symbol"), 50),
        rule_overrides=overrides,
    )
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _crypto_backtest_html(payload)
    return JSONResponse(payload)


async def fallback_premove_blueprint(request: Request) -> JSONResponse | HTMLResponse:
    result = container.premove_blueprint.blueprint()
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _blueprint_html(payload, "Trading Monster Blueprint")
    return JSONResponse(payload)


async def fallback_feature_registry(request: Request) -> JSONResponse | HTMLResponse:
    result = container.premove_blueprint.feature_registry()
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _blueprint_html(payload, "Feature Registry")
    return JSONResponse(payload)


async def fallback_scoring_model(request: Request) -> JSONResponse | HTMLResponse:
    result = container.premove_blueprint.scoring_model()
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _blueprint_html(payload, "Scoring Model")
    return JSONResponse(payload)


async def fallback_explain_premove_score(request: Request) -> JSONResponse:
    body = await request.json()
    snapshot = body.get("snapshot") if isinstance(body.get("snapshot"), dict) else body
    result = container.premove_blueprint.explain_candidate_score(snapshot)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_build_evidence_packet(request: Request) -> JSONResponse:
    body = await request.json()
    source = str(body.get("source") or "browser_fallback") if isinstance(body, dict) else "browser_fallback"
    item = body.get("item") if isinstance(body, dict) and isinstance(body.get("item"), dict) else body
    result = container.evidence_packets.build_packet(item, source)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_build_evidence_packets_from_scan(request: Request) -> JSONResponse:
    body = await request.json()
    source = str(body.get("source") or "browser_fallback_scan") if isinstance(body, dict) else "browser_fallback_scan"
    scan_result = body.get("scan_result") if isinstance(body, dict) and isinstance(body.get("scan_result"), dict) else body
    result = container.evidence_packets.build_packets_from_scan(scan_result, source)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_evidence_summary(request: Request) -> JSONResponse:
    if request.method == "POST":
        body = await request.json()
        packets = body.get("packets") if isinstance(body.get("packets"), list) else None
        limit = _int_or_default(str(body.get("limit")) if body.get("limit") is not None else None, 100)
    else:
        packets = None
        limit = _int_or_default(request.query_params.get("limit"), 100)
    result = container.evidence_packets.summarize_packets(packets, limit)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_health_full(request: Request) -> JSONResponse | HTMLResponse:
    listed_tools = await container.mcp.list_tools() if hasattr(container, "mcp") else await _mcp_tools_for_debug()
    names = [getattr(tool, "name", str(tool)) for tool in listed_tools]
    expected = request.query_params.get("expected_build_version")
    result = await container.debug_validation.full_health(names, expected)
    status_code = 200 if result["status"] == "OK" else 409
    payload = _review_only_envelope({"result": result})
    if _wants_html(request):
        return _health_full_html(payload)
    return JSONResponse(payload, status_code=status_code)


async def fallback_debug_tool_manifest(request: Request) -> JSONResponse:
    listed_tools = await _mcp_tools_for_debug()
    result = await container.debug_validation.tool_manifest(listed_tools)
    return JSONResponse(_review_only_envelope({"result": result}))


async def fallback_debug_scan_schema(request: Request) -> JSONResponse:
    expected = request.query_params.get("expected_build_version")
    result = container.debug_validation.scan_schema_example(expected)
    status_code = 200 if result["status"] == "SCAN_SCHEMA_READY" else 409
    return JSONResponse(_review_only_envelope({"result": result}), status_code=status_code)


async def _mcp_tools_for_debug() -> list[Any]:
    from app.mcp_server import mcp

    return await mcp.list_tools()
