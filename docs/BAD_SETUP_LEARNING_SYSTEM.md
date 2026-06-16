# Bad Setup Learning System

## Purpose

Use paper trading to turn weak, failed, or noisy setups into structured training data without weakening live-cash gates.

The live executor should keep rejecting bad setups. The paper learner should still record what would have happened if the system had:

- Avoided the setup.
- Taken a reduced same-side trade.
- Reversed the setup.
- Hedged the setup.
- Converted the setup into an options structure.

## Core Design

Every candidate becomes a state-action record:

- `state`: symbol, asset class, setup family, timestamp, price, volume, relative volume, spread, quote age, trend context, VWAP context, catalyst context, options-chain quality when relevant.
- `action`: avoid, long, short/reverse, reduced-size long, option call, option put, spread, hedge, or watch-only.
- `execution_model`: bid/ask, expected slippage, fees, borrow or margin constraint, contract liquidity, order type, time in force.
- `outcome`: MFE, MAE, exit reason, realized or simulated P/L, slippage, regret versus alternatives.

Cash gates consume only mature rules. Paper learning can explore setups that cash gates reject.

## Event Flow

1. Scanner emits candidate plus evidence packet.
2. Gatekeeper classifies the candidate as `cash_eligible`, `paper_only`, or `reject_log_only`.
3. Paper engine records the base candidate and all feasible counterfactual actions.
4. Execution simulator or Alpaca paper route records fills and misses.
5. Outcome worker marks MFE, MAE, P/L, slippage, and regret after fixed horizons.
6. Learning worker updates setup-level statistics and proposes rule changes.
7. Live promotion requires enough sample size, positive net expectancy after friction, and no risk-rule violations.

## Setup Families

Track these as first-class tags:

- Top mover continuation.
- Failed breakout.
- VWAP reclaim.
- VWAP rejection.
- Parabolic exhaustion.
- Continuation trap.
- Short squeeze or squeeze failure.
- Wide-spread trap.
- Options-chain quality failure.
- News/catalyst fade.

## Options Quality Gate

Options paper trials must record:

- Bid, ask, midpoint, spread percentage, quote age.
- Bid size and ask size when available.
- Volume and open interest.
- Expiration, strike, delta, IV, and contract multiplier.
- Whether the order was realistically fillable.

Do not promote options rules to cash unless the chain quality gate remains profitable after spread and slippage.

## Learning Metrics

Minimum stored metrics:

- Net expectancy by setup family and action.
- Feasibility rate.
- Average slippage and spread cost.
- MFE/MAE distribution.
- Regret versus best feasible action.
- Win rate, payoff ratio, and tail loss.
- Posterior confidence and sample size.
- Live-gate false positive and false negative rate.

## Promotion Rule

A paper-derived rule can only reach live-cash review when:

- It has enough closed samples for the setup family.
- Net expectancy remains positive after conservative friction.
- Max drawdown and tail-loss behavior fit the account risk budget.
- It does not require unavailable broker tools.
- It has a rollback condition and daily kill switch.

