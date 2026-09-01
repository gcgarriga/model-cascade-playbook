"""When a cascade can pay for itself, stated as two conditions.

A cascade adds a small-tier attempt and a routing signal in front of the large
tier. Both are paid on *every* request, including the ones that escalate and
buy the large-tier answer anyway. That gives a ceiling on how often a cascade
can escalate before it costs more than simply calling the large tier, and the
ceiling does not depend on how good the signal is.

Sums here are exact. The break-even ratio is a division, so it carries the
`Decimal` context's precision rather than being exact.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from examples.cascade_costs import ZERO, require_nonnegative


@dataclass(frozen=True)
class TierPrices:
    """Per-request costs, in any consistent unit.

    `small` and `large` are the cost of one attempt at that tier. `signal` is
    whatever the routing evidence costs per request: extra calls, extra tokens,
    a critic pass. A signal computed from samples the system already paid for
    has a `signal` of zero, but only because those samples are already in
    `small`.
    """

    small: Decimal
    large: Decimal
    signal: Decimal = ZERO

    def __post_init__(self) -> None:
        require_nonnegative(self.small, "small cost")
        require_nonnegative(self.large, "large cost")
        require_nonnegative(self.signal, "signal cost")
        if self.large == ZERO:
            raise ValueError("large cost must be positive to compare against it")

    @property
    def overhead(self) -> Decimal:
        """What the cascade pays before it has escalated anything."""
        return self.small + self.signal


def break_even_escalation_rate(prices: TierPrices) -> Decimal:
    """The highest escalation rate at which a cascade still undercuts big-only.

    Per request, a cascade pays `small + signal + rate * large`, while calling
    the large tier directly pays `large`. Setting them equal and solving for
    the rate gives:

        rate* = 1 - (small + signal) / large

    Escalate more often than `rate*` and the cascade is more expensive than
    big-only no matter how accurate the routing is. The result is clamped to
    [0, 1]: a zero means no escalation rate makes this cascade cheaper, because
    the small attempt plus its signal already cost at least as much as the
    large tier they were supposed to avoid.
    """
    rate = Decimal(1) - prices.overhead / prices.large
    if rate < ZERO:
        return ZERO
    if rate > Decimal(1):
        return Decimal(1)
    return rate


def cascade_cost_per_request(prices: TierPrices, escalation_rate: Decimal) -> Decimal:
    """Expected per-request cost of the cascade at a given escalation rate."""
    _require_rate(escalation_rate)
    return prices.overhead + escalation_rate * prices.large


def savings_per_request(prices: TierPrices, escalation_rate: Decimal) -> Decimal:
    """Big-only cost minus cascade cost. Negative means the cascade costs more."""
    return prices.large - cascade_cost_per_request(prices, escalation_rate)


def quality_condition_holds(
    retained_quality: Decimal, large_tier_quality: Decimal
) -> bool:
    """Whether the answers the cascade keeps are worth keeping.

    Cascade quality is `(1 - rate) * retained + rate * large`. Requiring that
    to be at least `large` reduces to `retained >= large`: the escalation rate
    cancels out entirely.

    So the quality test is not "does the cascade escalate enough" but "are the
    small-tier answers the policy *retains* as good as the large-tier answers
    it declined to buy". A signal that retains weaker answers loses quality at
    every escalation rate, and escalating more only trades that loss for the
    cost problem above.
    """
    for value, name in (
        (retained_quality, "retained quality"),
        (large_tier_quality, "large-tier quality"),
    ):
        require_nonnegative(value, name)
        if value > Decimal(1):
            raise ValueError(f"{name} must be between 0 and 1")
    return retained_quality >= large_tier_quality


def format_amount(value: Decimal) -> str:
    """Render a cost without the trailing zeros arithmetic scale leaves behind.

    `Decimal` preserves scale through multiplication, so a saving can arrive as
    `0.0030` purely because the large-tier price was written `0.010`. Normalize
    for display, and format with `f` so a normalized integer does not come back
    in exponent form.
    """
    return f"{value.normalize():f}"


def _require_rate(rate: Decimal) -> None:
    require_nonnegative(rate, "escalation rate")
    if rate > Decimal(1):
        raise ValueError("escalation rate must be between 0 and 1")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Report the escalation rate above which a cascade costs more than "
            "calling the large tier directly."
        )
    )
    parser.add_argument(
        "--small-cost",
        type=Decimal,
        required=True,
        help="Cost of one small-tier attempt, per request.",
    )
    parser.add_argument(
        "--large-cost",
        type=Decimal,
        required=True,
        help="Cost of one large-tier attempt, per request.",
    )
    parser.add_argument(
        "--signal-cost",
        type=Decimal,
        default=ZERO,
        help="Cost of the routing signal, per request (default: 0).",
    )
    parser.add_argument(
        "--escalation-rate",
        type=Decimal,
        default=None,
        help="Your measured escalation rate, to compare against break-even.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        prices = TierPrices(
            small=args.small_cost,
            large=args.large_cost,
            signal=args.signal_cost,
        )
        rate = break_even_escalation_rate(prices)
        if args.escalation_rate is not None:
            _require_rate(args.escalation_rate)
    except (ValueError, ArithmeticError) as error:
        parser.error(str(error))

    print(f"overhead per request (small + signal): {format_amount(prices.overhead)}")
    print(f"break-even escalation rate: {rate:.4f}")

    if rate == ZERO:
        print(
            "verdict: no escalation rate is cheaper than big-only -- the small "
            "attempt and its signal already cost at least as much as the large "
            "tier"
        )
        return 0

    if args.escalation_rate is None:
        print(
            "verdict: escalate less often than the break-even rate, and check "
            "that retained answers match large-tier quality"
        )
        return 0

    saving = savings_per_request(prices, args.escalation_rate)
    if args.escalation_rate < rate:
        print(f"verdict: cheaper than big-only by {format_amount(saving)} per request")
    elif args.escalation_rate == rate:
        print("verdict: exactly break-even with big-only, before fixed costs")
    else:
        print(
            f"verdict: more expensive than big-only by {format_amount(-saving)} "
            "per request"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
