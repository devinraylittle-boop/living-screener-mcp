from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.enums import Direction, OrderType


@dataclass(frozen=True)
class Quote:
    ticker: str
    price: float
    previous_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    timestamp: datetime | None = None
    provider: str = "unknown"
    bid: float | None = None
    ask: float | None = None
    is_stale: bool = False


@dataclass(frozen=True)
class Candle:
    ticker: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    interval: str
    provider: str = "unknown"


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    bid: float
    ask: float
    volume: int
    open_interest: int
    days_to_expiration: int | None = None
    lottery_risk: bool = False


@dataclass(frozen=True)
class TradePlan:
    ticker: str
    direction: Direction
    setup_type: str
    account_value: float
    proposed_risk_dollars: float
    order_type: OrderType = OrderType.LIMIT
    is_options_trade: bool = False
    is_zero_dte: bool = False
    requested_execution: bool = False
    approval_text: str | None = None
    option_contract: OptionContract | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
