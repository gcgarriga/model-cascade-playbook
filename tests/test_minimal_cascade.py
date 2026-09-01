from __future__ import annotations

import math

import pytest

from examples.minimal_cascade import (
    Candidate,
    Cascade,
    RouteReason,
    ThresholdPolicy,
    main,
)


class StubTier:
    def __init__(self, candidate: Candidate) -> None:
        self.candidate = candidate
        self.calls: list[str] = []

    def generate(self, prompt: str) -> Candidate:
        self.calls.append(prompt)
        return self.candidate


def test_retains_small_answer_at_threshold() -> None:
    small = StubTier(Candidate(text="small answer", confidence=0.7))
    large = StubTier(Candidate(text="large answer", confidence=None))
    cascade = Cascade(small=small, large=large, policy=ThresholdPolicy(0.7))

    result = cascade.run("example prompt")

    assert result.answer == "small answer"
    assert result.selected_tier == "small"
    assert result.reason is RouteReason.SCORE_AT_OR_ABOVE_THRESHOLD
    assert small.calls == ["example prompt"]
    assert large.calls == []


def test_escalates_low_confidence_answer_once() -> None:
    small = StubTier(Candidate(text="small answer", confidence=0.69))
    large = StubTier(Candidate(text="large answer", confidence=None))
    cascade = Cascade(small=small, large=large, policy=ThresholdPolicy(0.7))

    result = cascade.run("example prompt")

    assert result.answer == "large answer"
    assert result.selected_tier == "large"
    assert result.reason is RouteReason.SCORE_BELOW_THRESHOLD
    assert small.calls == ["example prompt"]
    assert large.calls == ["example prompt"]


def test_missing_signal_escalates_conservatively() -> None:
    small = StubTier(Candidate(text="small answer", confidence=None))
    large = StubTier(Candidate(text="large answer", confidence=None))
    cascade = Cascade(small=small, large=large, policy=ThresholdPolicy(0.7))

    result = cascade.run("example prompt")

    assert result.selected_tier == "large"
    assert result.reason is RouteReason.MISSING_SIGNAL


@pytest.mark.parametrize("confidence", [math.nan, math.inf, -0.01, 1.01])
def test_malformed_signal_escalates_conservatively(confidence: float) -> None:
    small = StubTier(Candidate(text="small answer", confidence=confidence))
    large = StubTier(Candidate(text="large answer", confidence=None))
    cascade = Cascade(small=small, large=large, policy=ThresholdPolicy(0.7))

    result = cascade.run("example prompt")

    assert result.selected_tier == "large"
    assert result.reason is RouteReason.MALFORMED_SIGNAL


@pytest.mark.parametrize("threshold", [math.nan, math.inf, -0.01, 1.01])
def test_invalid_threshold_is_rejected(threshold: float) -> None:
    with pytest.raises(ValueError, match="threshold must be finite and between"):
        ThresholdPolicy(threshold)


@pytest.mark.parametrize(
    ("confidence", "selected_tier", "reason"),
    [
        ("0.9", "small", RouteReason.SCORE_AT_OR_ABOVE_THRESHOLD),
        ("0.3", "large", RouteReason.SCORE_BELOW_THRESHOLD),
    ],
)
def test_cli_demonstrates_both_routes(
    confidence: str,
    selected_tier: str,
    reason: RouteReason,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["example prompt", "--small-confidence", confidence])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        f"selected_tier={selected_tier}",
        f"reason={reason}",
        f"answer={selected_tier} tier simulated answer for: example prompt",
    ]


def test_cli_reports_invalid_threshold_as_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["example prompt", "--threshold", "1.01"])

    assert exit_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "error: threshold must be finite and between 0 and 1" in stderr
    assert "Traceback" not in stderr
