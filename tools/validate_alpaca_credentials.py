from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def normalize_base_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    if cleaned.lower().endswith("/v2"):
        return cleaned[:-3].rstrip("/")
    return cleaned


def endpoint_environment(base_url: str) -> str:
    host = base_url.lower()
    if "paper-api.alpaca.markets" in host:
        return "paper"
    if "api.alpaca.markets" in host:
        return "live"
    return "custom"


def request_json(base_url: str, path: str, headers: dict[str, str], timeout: int = 20) -> Any:
    request = Request(base_url.rstrip("/") + path, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def http_error_summary(exc: HTTPError) -> dict[str, Any]:
    body = ""
    try:
        body = exc.read().decode("utf-8")
    except Exception:  # noqa: BLE001 - error body is diagnostic only
        body = ""
    return {
        "status": exc.code,
        "reason": exc.reason,
        "x_request_id": exc.headers.get("x-request-id") or exc.headers.get("X-Request-ID"),
        "body": body[:500],
    }


def sanitized_account(account: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "status",
        "account_blocked",
        "trading_blocked",
        "transfers_blocked",
        "trade_suspended_by_user",
        "crypto_status",
        "options_approved_level",
        "options_trading_level",
        "buying_power",
        "cash",
        "portfolio_value",
        "equity",
    ]
    return {key: account.get(key) for key in keys}


def main() -> int:
    configured_base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    base_url = normalize_base_url(configured_base_url)
    expected_environment = os.getenv("ALPACA_EXPECTED_ENV", "").strip().lower()
    key_id = os.getenv("ALPACA_API_KEY_ID", "").strip()
    secret = os.getenv("ALPACA_API_SECRET_KEY", "").strip()
    actual_environment = endpoint_environment(base_url)
    result: dict[str, Any] = {
        "broker": "alpaca",
        "base_url": base_url,
        "normalized_base_url": base_url != configured_base_url.strip().rstrip("/"),
        "endpoint_environment": actual_environment,
        "expected_environment": expected_environment or None,
        "environment_warning": None,
        "has_key_id": bool(key_id),
        "has_secret_key": bool(secret),
        "account_ready": False,
        "crypto_assets_ready": False,
        "options_contracts_ready": False,
    }
    if not key_id or not secret:
        result["status"] = "MISSING_CREDENTIALS"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2

    if expected_environment and actual_environment != expected_environment:
        result["environment_warning"] = (
            f"Expected {expected_environment} credentials, but ALPACA_BASE_URL points to {actual_environment}. "
            "Alpaca paper and live Trading API credentials are not interchangeable."
        )

    headers = {
        "APCA-API-KEY-ID": key_id,
        "APCA-API-SECRET-KEY": secret,
        "accept": "application/json",
        "user-agent": "living-screener-alpaca-validator/1.0",
    }
    try:
        account = request_json(base_url, "/v2/account", headers)
        result["account"] = sanitized_account(account if isinstance(account, dict) else {})
        result["account_ready"] = bool(isinstance(account, dict) and account.get("status") == "ACTIVE" and not account.get("trading_blocked"))
    except HTTPError as exc:
        result["account_error"] = http_error_summary(exc)
    except (URLError, TimeoutError, OSError) as exc:
        result["account_error"] = type(exc).__name__

    try:
        assets = request_json(base_url, "/v2/assets?asset_class=crypto&status=active", headers)
        result["crypto_asset_count"] = len(assets) if isinstance(assets, list) else 0
        result["crypto_assets_ready"] = bool(result["crypto_asset_count"])
    except HTTPError as exc:
        result["crypto_assets_error"] = http_error_summary(exc)
    except (URLError, TimeoutError, OSError) as exc:
        result["crypto_assets_error"] = type(exc).__name__

    try:
        query = urlencode({"underlying_symbols": "SPY", "status": "active", "limit": 1})
        options = request_json(base_url, f"/v2/options/contracts?{query}", headers)
        contracts = options.get("option_contracts") if isinstance(options, dict) else []
        result["option_contract_probe_count"] = len(contracts or [])
        result["options_contracts_ready"] = bool(contracts)
    except HTTPError as exc:
        result["options_contracts_error"] = http_error_summary(exc)
    except (URLError, TimeoutError, OSError) as exc:
        result["options_contracts_error"] = type(exc).__name__

    result["status"] = "ALPACA_VALIDATION_READY" if result["account_ready"] else "ALPACA_VALIDATION_BLOCKED"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["account_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
