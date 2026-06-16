# Broker Credential Setup

## Alpaca

Use environment variables. Do not paste keys into code, docs, logs, or committed files.

Paper validation:

```powershell
$env:ALPACA_BASE_URL="https://paper-api.alpaca.markets"
$env:ALPACA_DATA_URL="https://data.alpaca.markets"
$env:ALPACA_EXPECTED_ENV="paper"
$env:ALPACA_API_KEY_ID="<paper key id>"
$env:ALPACA_API_SECRET_KEY="<paper secret key>"
python tools/validate_alpaca_credentials.py
```

Live validation, read-only proof only:

```powershell
$env:ALPACA_LIVE_BASE_URL="https://api.alpaca.markets"
$env:ALPACA_DATA_URL="https://data.alpaca.markets"
$env:ALPACA_LIVE_API_KEY_ID="<live key id>"
$env:ALPACA_LIVE_API_SECRET_KEY="<live secret key>"
powershell -ExecutionPolicy Bypass -File tools/status_alpaca_live_account.ps1
```

The validator prints sanitized account status, buying power, options level, crypto status, crypto asset probe, and options contract probe. It does not place orders and does not print secrets.

`ALPACA_BASE_URL` may include or omit the `/v2` suffix. The validator and bridge normalize it before making requests.

For autonomous live cash, keep live Alpaca keys in `ALPACA_LIVE_API_KEY_ID`
and `ALPACA_LIVE_API_SECRET_KEY`. Do not reuse paper-key variables for the
live endpoint.

Alpaca's official authentication docs say paper Trading API calls use `paper-api.alpaca.markets`, while live Trading API calls use `api.alpaca.markets`. If a key returns `401` on `paper-api.alpaca.markets` but works on `api.alpaca.markets`, treat it as a live key and do not use it for paper automation.

2026-06-16 status: paper credentials validated against `https://paper-api.alpaca.markets`; paper options and crypto capability probes passed. No order was placed.

If the dashboard is in Paper Trading mode but the API Keys panel shows endpoint `https://api.alpaca.markets`, try one of these:

1. Use the left sidebar `API` page while the account selector says Paper Trading, then regenerate keys there.
2. Look for a paper-specific API key section or a paper account reset/regenerate button.
3. If the generated card still shows `https://api.alpaca.markets`, contact Alpaca support and ask why the Paper Trading account API card is issuing live-endpoint Trading API credentials.

Support message template:

```text
My Trading Dashboard account selector is set to Paper Trading, but the API Keys panel shows Endpoint: https://api.alpaca.markets. The generated key works on https://api.alpaca.markets/v2/account but returns 401 on https://paper-api.alpaca.markets/v2/account. Alpaca documentation says paper Trading API calls should use paper-api.alpaca.markets and paper/live credentials are separate. Can you confirm how I should generate keys for the paper endpoint for paper account <paper account id>?

Paper request x-request-id: <paste from tools/validate_alpaca_credentials.py output>
```

## Robinhood

Robinhood credentials stay inside the Robinhood MCP OAuth connection. Do not store Robinhood passwords, tokens, or cookies in this repo.

Current Codex proof:

- Agentic account is active.
- Equity account/portfolio/position/order/tradability/review tools are exposed.
- Options order tools are not exposed in this session.
- Crypto order tools are not exposed in this session.

Before live equity automation, verify:

1. Portfolio and buying power.
2. Open positions.
3. Open orders.
4. Tradability for candidate symbols.
5. `review_equity_order` for the exact order.
6. Explicit live authorization before `place_equity_order`.
