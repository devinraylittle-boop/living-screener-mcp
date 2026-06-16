# Autonomy Authorization Decision - 2026-06-16

Operator request:

- Enable full autonomy.
- Codex has control across all accounts.

System decision:

- Full live autonomy is refused.
- Limited Stage 3 live operation remains allowed only for small, human-approved Robinhood equity trades.
- Stage 2 Alpaca paper automation is allowed and should be used aggressively for research and data gathering.

Reason:

The system is classified as `limited_live_trading_ready`, not fully autonomous ready. Full autonomy is blocked by missing production-grade paper sample size, external alerting, broker reconciliation, secrets rotation, operator runbook, and strategy promotion evidence.

Current allowed lanes:

- Alpaca paper: autonomous paper trading and counterfactual research.
- Robinhood live: human-approved small equity orders only.

Current blocked lanes:

- Full autonomous live trading.
- Autonomous live options.
- Autonomous live crypto.
- Any live strategy not promoted from paper evidence.
- Any live order while market data, broker review, quote/spread, journal, reconciliation, or loss-limit gates fail.

Enforcement:

- `config/autonomous_readiness_gates.json` keeps `global_live_default=false`.
- `tools/stock_bridge_loop.py` refuses live operation for Stage 4 or Stage 5.
- `AUTONOMY_STAGE=stage_5_full_autonomous_with_strict_caps` is explicitly refused by tests until readiness gates are satisfied.

Next action:

Use the authorization to push the safe lanes harder:

1. Run Alpaca paper automation.
2. Build the paper lifecycle ledger.
3. Add broker reconciliation.
4. Add external alerts and kill switch.
5. Promote strategies only after closed paper evidence passes the readiness gates.

