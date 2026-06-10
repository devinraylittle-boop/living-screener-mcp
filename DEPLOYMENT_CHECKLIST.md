# Fresh Deploy Checklist

Upload the contents of the clean release folder or zip. Do not upload the parent folder itself.

## Upload

- `.dockerignore`
- `.env.example`
- `.gitignore`
- `DEPLOYMENT_CHECKLIST.md`
- `Dockerfile`
- `README.md`
- `app/`
- `data/`
- `docs/`
- `docker-compose.yml`
- `living_screener.py`
- `mcp_server.py`
- `pyproject.toml`
- `railway.json`
- `render.yaml`
- `requirements.txt`
- `screener_config.json`
- `tests/`
- `tools/`

## Do Not Upload

- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- old release folders
- old zip files
- `robinhood-mcp-login.log`
- `data/living_screener.sqlite3`

## Render Secret

Set only this secret manually in Render:

```text
FINNHUB_API_KEY=<your key>
```

The included `render.yaml` uses Render's free web-service plan. That is good for first live testing, but it does not preserve local SQLite journal history across restarts.

After redeploy, open `/tools` and confirm `run_scalp_scan`, `review_candidate_for_options`, and `review_pending_buy_order` appear before reconnecting ChatGPT.
