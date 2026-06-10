from enum import StrEnum


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"
    CALL = "call"
    PUT = "put"


class OrderType(StrEnum):
    LIMIT = "limit"
    MARKET = "market"


class RiskStatus(StrEnum):
    APPROVE_FOR_REVIEW = "APPROVE_FOR_REVIEW"
    WARN = "WARN"
    SOFT_STOP = "SOFT_STOP"
    BLOCK = "BLOCK"
    HARD_LOCKOUT = "HARD_LOCKOUT"
