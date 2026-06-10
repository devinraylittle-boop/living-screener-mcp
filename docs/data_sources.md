# Data Sources

Primary live setup:

- Quotes: Finnhub.
- Candles: Finnhub first, then yfinance fallback if Finnhub returns no candle data.

Finnhub quote data is useful on the free account. Finnhub stock candles may require paid access, so missing candles are expected on some free accounts. The fallback keeps the scanner useful while preserving PASS-first behavior.

Freshness is market-aware. During regular market hours, stale thresholds are strict. Outside regular market hours, the scanner can accept data from the latest regular-session close, including weekends, instead of forcing a false stale rejection.

Options-chain validation uses yfinance as a free starting point. A contract must have valid bid/ask, acceptable spread, minimum volume, minimum open interest, allowed expiration range, and calculable max loss before the MCP can produce a review-only options plan.

Configured through `MARKET_DATA_PROVIDER`.

Supported:

- `finnhub`
- `yfinance`
- `polygon` stub
- `none`

Provider errors fail closed into PASS.
