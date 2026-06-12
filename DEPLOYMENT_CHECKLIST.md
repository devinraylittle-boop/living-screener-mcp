# Fresh Deploy Checklist

Target build:

```text
2026.06.12-full-crypto-universe
```

Upload the contents of the clean release folder or zip. Do not upload the parent folder itself.

If using GitHub's web uploader, open the zip locally and upload the files/folders inside it to the repository root. The repository root should contain `app/`, `docs/`, `tools/`, `render.yaml`, `requirements.txt`, and `Dockerfile` directly. Do not upload the zip as a single file, and do not upload a nested folder named `living-screener-mcp-manual-snapshot-form-20260610-090000`.

## Upload

- `.dockerignore`
- `.env.example`
- `.gitignore`
- `DEPLOYMENT_CHECKLIST.md`
- `Dockerfile`
- `README.md`
- `RELEASE_MANIFEST.json`
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

## Quick Root Check

After uploading, the repository root should look like this:

```text
app/
docs/
tests/
tools/
Dockerfile
README.md
render.yaml
requirements.txt
```

If those files appear inside a nested release folder, Render will keep building the old code.

For a compact fingerprint of the expected release, open:

```text
RELEASE_MANIFEST.json
```

## Render Secret

Set only this secret manually in Render:

```text
FINNHUB_API_KEY=<your key>
```

The included `render.yaml` uses Render's free web-service plan. That is good for first live testing, but it does not preserve local SQLite journal history across restarts.

## After Redeploy

From the package folder, run:

```powershell
.\tools\watch_deploy.ps1
```

It waits for the deployed build to become `2026.06.12-full-crypto-universe`, then runs live validation.

Minimum live checks:

```text
/version -> build_version 2026.06.12-full-crypto-universe
/tools -> tool_count 96
/release-manifest -> target_build_version 2026.06.12-full-crypto-universe
/health/full?expected_build_version=2026.06.12-full-crypto-universe -> status OK
/ -> Tomorrow Operator Brief
/ops/go-live-rehearsal?account_value=50&format=html -> Go-Live Rehearsal
/trade/manual-form?format=html -> Manual Snapshot Form
```

After that passes, reconnect ChatGPT to the app and run the connector check prompt from `docs/TOMORROW_MARKET_RUNBOOK.md`.
