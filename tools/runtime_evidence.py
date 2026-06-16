from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_EVIDENCE_PATH = ROOT / "config" / "runtime_readiness_evidence.json"


def load_json(path: Path) -> tuple[dict[str, Any], bool, str | None]:
    if not path.exists():
        return {}, False, "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, False, repr(exc)
    if not isinstance(data, dict):
        return {}, False, "top-level JSON value must be an object"
    return data, True, None


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "on", "passed"}


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and any(str(item).strip() for item in value)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    return value if isinstance(value, dict) else {}


def build_runtime_evidence_report(path: Path | None = None) -> dict[str, Any]:
    path = path or Path(os.getenv("RUNTIME_READINESS_EVIDENCE_PATH", "") or DEFAULT_RUNTIME_EVIDENCE_PATH)
    evidence, readable, error = load_json(path)

    alerting = _section(evidence, "external_alerting")
    secrets = _section(evidence, "secrets_rotation")
    model_review = _section(evidence, "monthly_model_review")

    checks = {
        "evidence_file_readable": readable,
        "external_alerting_enabled": _truthy(alerting.get("enabled")),
        "external_alerting_channel_configured": _nonempty_list(alerting.get("channels")),
        "external_alerting_last_test_passed": _truthy(alerting.get("last_test_status")),
        "external_monitoring_outside_local_machine": _truthy(alerting.get("monitoring_outside_local_machine")),
        "secrets_rotation_confirmed": _truthy(secrets.get("confirmed")),
        "secrets_rotation_operator_confirmed": _truthy(secrets.get("operator_confirmed")),
        "live_broker_keys_separated": _truthy(secrets.get("live_broker_keys_separated")),
        "no_live_secrets_in_package": _truthy(secrets.get("no_live_secrets_in_package")),
        "monthly_model_review_established": _truthy(model_review.get("established")),
    }

    external_alerting_ready = all(
        checks[name]
        for name in [
            "evidence_file_readable",
            "external_alerting_enabled",
            "external_alerting_channel_configured",
            "external_alerting_last_test_passed",
            "external_monitoring_outside_local_machine",
        ]
    )
    secrets_rotation_ready = all(
        checks[name]
        for name in [
            "evidence_file_readable",
            "secrets_rotation_confirmed",
            "secrets_rotation_operator_confirmed",
            "live_broker_keys_separated",
            "no_live_secrets_in_package",
        ]
    )
    monthly_model_review_ready = checks["evidence_file_readable"] and checks["monthly_model_review_established"]

    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "status": "RUNTIME_EVIDENCE_READY" if external_alerting_ready and secrets_rotation_ready else "RUNTIME_EVIDENCE_BLOCKED",
        "review_only": True,
        "can_place_order_from_this_report": False,
        "source": str(path),
        "checks": checks,
        "blockers": blockers,
        "external_alerting_ready": external_alerting_ready,
        "secrets_rotation_ready": secrets_rotation_ready,
        "monthly_model_review_ready": monthly_model_review_ready,
        "last_alert_test_at": alerting.get("last_test_at"),
        "secrets_rotated_at": secrets.get("rotated_at"),
        "monthly_model_review_next_due": model_review.get("next_due"),
        "errors": {"evidence": error},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate runtime readiness evidence without placing orders.")
    parser.add_argument("--path", type=Path, help="Optional runtime evidence JSON path.")
    args = parser.parse_args(argv)
    print(json.dumps(build_runtime_evidence_report(args.path), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
