"""Shared cost records for the offline cascade examples.

Imported by the economics and evaluator examples; this module is not a CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")


def require_nonnegative(value: Decimal, name: str) -> None:
    if not value.is_finite() or value < ZERO:
        raise ValueError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None = None

    def __post_init__(self) -> None:
        values = (self.input_tokens, self.output_tokens)
        if any(not isinstance(value, int) or value < 0 for value in values):
            raise ValueError("token counts must be nonnegative integers")
        if self.reasoning_tokens is not None and (
            not isinstance(self.reasoning_tokens, int) or self.reasoning_tokens < 0
        ):
            raise ValueError("reasoning tokens must be a nonnegative integer or None")


@dataclass(frozen=True)
class PricedUsage:
    variable_cost: Decimal
    reasoning_included: bool

    def __post_init__(self) -> None:
        require_nonnegative(self.variable_cost, "variable cost")


@dataclass(frozen=True)
class TokenRates:
    input_per_token: Decimal
    output_per_token: Decimal
    reasoning_per_token: Decimal | None = None

    def __post_init__(self) -> None:
        require_nonnegative(self.input_per_token, "input rate")
        require_nonnegative(self.output_per_token, "output rate")
        if self.reasoning_per_token is not None:
            require_nonnegative(self.reasoning_per_token, "reasoning rate")

    def price(self, usage: TokenUsage) -> PricedUsage:
        known = (
            Decimal(usage.input_tokens) * self.input_per_token
            + Decimal(usage.output_tokens) * self.output_per_token
        )
        # Bind both optionals to locals so the type checker narrows them
        # directly. The previous form needed `assert` to re-establish what the
        # flag already implied, and `assert` is stripped under `python -O`.
        reasoning_tokens = usage.reasoning_tokens
        reasoning_rate = self.reasoning_per_token
        if reasoning_tokens is not None and reasoning_rate is not None:
            known += Decimal(reasoning_tokens) * reasoning_rate
            return PricedUsage(known, reasoning_included=True)
        return PricedUsage(known, reasoning_included=False)


@dataclass(frozen=True)
class CostBreakdown:
    signal: Decimal
    variable: Decimal
    fixed: Decimal
    reasoning_included: bool

    @property
    def total(self) -> Decimal:
        return self.signal + self.variable + self.fixed
