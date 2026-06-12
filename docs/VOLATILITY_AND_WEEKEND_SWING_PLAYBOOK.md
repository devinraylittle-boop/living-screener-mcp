# Volatility And Weekend Swing Playbook

Purpose: keep volatile names in the system, but stop treating them like ordinary scalps.

## Core Principle

Volatile names are allowed only when the system pays for the volatility with wider logic, smaller size, better confirmation, and stricter execution quality. A volatile ticker is not a reason to avoid trading; it is a reason to demand a cleaner setup.

## Lanes

### Lane 1: Intraday Volatility Scalp

Use during regular market hours when the goal is a fast capture.

Requirements:

- Fresh broker quote.
- Spread not more than 12 bps for volatile names.
- No same-symbol stop-loss in the last 60 minutes.
- No more than one failed volatile trade in the last 30 minutes.
- Clear trend direction, not just movement.
- Entry should occur on continuation after a pullback or reclaim, not on a random spike.
- No new entries after two consecutive data or broker errors.

Sizing:

- A-grade volatile setup: up to 15 dollars.
- B-grade volatile setup: 5 to 10 dollars.
- Re-entry setup after prior loss: blocked unless score is 90+ and trend has materially reset.

Stops:

- Fixed 0.35% stop is too tight for volatile names.
- Volatile stop should be max of:
  - 0.55%
  - 3x current spread
  - nearest invalidation level from setup structure

Targets:

- Minimum target must be 1.5R.
- Prefer 2R if the name is moving cleanly.
- If price reaches +0.35% and stalls, tighten exit rather than letting a winner become a full stop.

### Lane 2: Trend Continuation Swing

Use late day when the goal is to hold overnight or over the weekend.

Requirements:

- Strong close candidate, not a midday chop candidate.
- Close near high of day for long trades, or constructive base with improving volume.
- Catalyst or sector tailwind is known and not likely to gap violently against the position.
- Avoid names with binary event risk unless position size is tiny.
- Avoid entering only because the stock already moved a lot.
- Do not swing if broker/data errors are active.

Sizing:

- Starter size only until the swing system has data.
- Max initial swing size: 5 to 10 dollars on a 100 dollar account.
- Increase only after positive swing expectancy is proven over at least 20 closed swings.

Stops:

- Swing stop cannot be the intraday scalp stop.
- Use structure-based invalidation, usually below late-day consolidation or prior higher low.
- If structure implies too much loss for the account, pass.

Targets:

- First target: next obvious resistance or 1.5R.
- If Friday swing, require a stronger reason than normal because two non-trading days add gap risk.

### Lane 3: After-Hours Trade Management

After-hours trading is not the same as regular-hours trading.

Allowed:

- Manage or exit existing positions when liquidity is acceptable.
- Review extended-hours quotes.
- Place limit orders only when broker rules and share quantity allow it.
- Open new positions in premarket/after-hours only through limit orders with whole-share quantity.

Restricted:

- Do not use dollar-based market orders after hours.
- Do not assume fractional market orders work after hours.
- Do not chase thin after-hours prints.
- Do not enter volatile names after hours unless spread and depth are unusually clean.
- Skip high-priced tickers when the available budget cannot buy at least one share by limit order.

Practical account constraint:

With a small account, many high-priced volatile names cannot be bought after hours through normal whole-share limit routing. Regular-hours fractional stock execution is much easier than after-hours stock execution.

### Lane 4: Weekend Risk

Stocks do not trade over the weekend, so weekend swings are gap-risk trades. Crypto can trade all weekend, but crypto should remain a separate lane with its own risk rules.

Weekend swing checklist:

- Is there a real catalyst into Monday?
- Is the ticker liquid enough to exit quickly Monday?
- Is the planned loss acceptable if Monday opens beyond the stop?
- Is the position small enough to survive bad news?
- Is the trade still attractive if entry slips by the spread?

If any answer is no, pass.

## Pass Rules

Pass on volatile stock entries when:

- Spread is wide relative to target.
- Price is between VWAP and resistance with no clean reclaim.
- Same ticker already stopped today.
- The move is extended and entry would chase the top of a candle.
- Broker/data errors appeared in the last two cycles.
- The expected target is less than 1.5R.
- The only reason to trade is fear of missing the move.

## Immediate System Rules

1. Keep volatile names, but split them into a volatile lane.
2. Use smaller size for volatile B-grade setups.
3. Use wider, structure-aware stops for volatile names.
4. Require stricter confirmation before re-entering a stopped volatile ticker.
5. Add a late-day swing scanner separate from scalp scanning.
6. Treat after-hours as limit-order-only review/management unless broker capability proves otherwise.
7. Halt new entries after repeated data or broker errors.

## What To Build Next

- Volatility bucket per ticker.
- Same-symbol cooldown after stop-loss.
- MFE/MAE tracker for every entry and skipped candidate.
- Late-day swing candidate endpoint.
- After-hours order capability checker.
- Weekend gap-risk score.
- Separate crypto weekend lane.
