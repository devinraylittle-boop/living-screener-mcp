# Architecture

Living Screener MCP is split into:

- `app/main.py`: hosted HTTP app
- `app/mcp_server.py`: MCP tools
- `app/data_adapters/`: market data providers
- `app/services/`: scanning, risk, journal, backtest, postmortem
- `app/storage/`: SQLite event logging

It has no broker execution code and no Robinhood API client.
