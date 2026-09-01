"""A deterministic teaching example of post-attempt model escalation.

The tiers below simulate model calls. They make no network requests and do not
measure real model quality.
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol, cast


@dataclass(frozen=True)
class Candidate:
    text: str
    confidence: float | None


class Tier(Protocol):
    def generate(self, prompt: str) -> Candidate: ...


class RouteReason(StrEnum):
    SCORE_AT_OR_ABOVE_THRESHOLD = "score-at-or-above-threshold"
    SCORE_BELOW_THRESHOLD = "score-below-threshold"
    MISSING_SIGNAL = "missing-signal"
    MALFORMED_SIGNAL = "malformed-signal"


@dataclass(frozen=True)
class RouteDecision:
    escalate: bool
    reason: RouteReason


@dataclass(frozen=True)
class ThresholdPolicy:
    threshold: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be finite and between 0 and 1")

    def decide(self, candidate: Candidate) -> RouteDecision:
        confidence = candidate.confidence
        if confidence is None:
            return RouteDecision(escalate=True, reason=RouteReason.MISSING_SIGNAL)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            return RouteDecision(escalate=True, reason=RouteReason.MALFORMED_SIGNAL)
        if confidence < self.threshold:
            return RouteDecision(
                escalate=True,
                reason=RouteReason.SCORE_BELOW_THRESHOLD,
            )
        return RouteDecision(
            escalate=False,
            reason=RouteReason.SCORE_AT_OR_ABOVE_THRESHOLD,
        )


@dataclass(frozen=True)
class CascadeResult:
    answer: str
    selected_tier: Literal["small", "large"]
    reason: RouteReason


@dataclass(frozen=True, kw_only=True)
class Cascade:
    small: Tier
    large: Tier
    policy: ThresholdPolicy

    def run(self, prompt: str) -> CascadeResult:
        small_candidate = self.small.generate(prompt)
        decision = self.policy.decide(small_candidate)
        if not decision.escalate:
            return CascadeResult(
                answer=small_candidate.text,
                selected_tier="small",
                reason=decision.reason,
            )

        large_candidate = self.large.generate(prompt)
        return CascadeResult(
            answer=large_candidate.text,
            selected_tier="large",
            reason=decision.reason,
        )


@dataclass(frozen=True)
class DemoTier:
    name: str
    confidence: float | None

    def generate(self, prompt: str) -> Candidate:
        return Candidate(
            text=f"{self.name} tier simulated answer for: {prompt}",
            confidence=self.confidence,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an offline simulation of a two-tier model cascade."
    )
    parser.add_argument("prompt", help="Prompt passed to both simulated tiers.")
    parser.add_argument(
        "--small-confidence",
        type=float,
        default=0.8,
        help="Simulated small-tier confidence score (default: 0.8).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Retain the small answer at or above this score (default: 0.7).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    small_confidence = cast(float, args.small_confidence)
    threshold = cast(float, args.threshold)
    prompt = cast(str, args.prompt)

    try:
        policy = ThresholdPolicy(threshold)
    except ValueError as error:
        parser.error(str(error))

    cascade = Cascade(
        small=DemoTier(name="small", confidence=small_confidence),
        large=DemoTier(name="large", confidence=None),
        policy=policy,
    )
    result = cascade.run(prompt)
    print(f"selected_tier={result.selected_tier}")
    print(f"reason={result.reason}")
    print(f"answer={result.answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
