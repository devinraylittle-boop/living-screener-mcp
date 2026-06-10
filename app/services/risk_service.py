from __future__ import annotations

from app.config import Settings
from app.models.enums import OrderType, RiskStatus
from app.models.schemas import TradePlan
from app.storage.repositories import EventRepository


class RiskService:
    def __init__(self, settings: Settings, events: EventRepository):
        self.settings = settings
        self.events = events

    def check(self, trade_plan: TradePlan) -> dict:
        reasons = []
        warnings = []
        if trade_plan.requested_execution:
            reasons.append("Execution is impossible from this MCP.")
        if trade_plan.order_type == OrderType.MARKET:
            reasons.append("Market orders are blocked.")
        if trade_plan.approval_text and trade_plan.approval_text != self.settings.approval_phrase:
            reasons.append("Vague or mismatched approval text rejected.")
        if trade_plan.proposed_risk_dollars > trade_plan.account_value * self.settings.max_trade_risk_pct:
            reasons.append("Risk exceeds configured cap.")
        if trade_plan.is_zero_dte:
            warnings.append("Zero-DTE is review/planning only.")
        status = RiskStatus.BLOCK.value if reasons else RiskStatus.APPROVE_FOR_REVIEW.value
        result = {
            "ticker": trade_plan.ticker.upper(),
            "status": status,
            "reasons": reasons,
            "warnings": warnings,
            "can_place_order_from_this_mcp": False,
            "execution_intent": {"broker_review_required": True, "can_place_order_from_this_mcp": False},
        }
        return self.events.log("risk_check", result)

    def daily_status(self, account_value: float, day_start_value: float) -> dict:
        drawdown = 0.0 if day_start_value <= 0 else max(0.0, (day_start_value - account_value) / day_start_value)
        status = "normal"
        if drawdown >= self.settings.hard_lockout_daily_drawdown_pct:
            status = RiskStatus.HARD_LOCKOUT.value
        elif drawdown >= self.settings.soft_stop_daily_drawdown_pct:
            status = RiskStatus.SOFT_STOP.value
        elif drawdown >= self.settings.warn_daily_drawdown_pct:
            status = RiskStatus.WARN.value
        return self.events.log("daily_status", {"status": status, "drawdown_pct": round(drawdown, 4)})
