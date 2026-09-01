from __future__ import annotations

import re
from decimal import Decimal

import pytest

from examples.cascade_economics import (
    TierPrices,
    break_even_escalation_rate,
    cascade_cost_per_request,
    format_amount,
    main,
    quality_condition_holds,
    savings_per_request,
)
from tests.support import ROOT

D = Decimal


def test_break_even_rate_matches_the_stated_formula() -> None:
    prices = TierPrices(small=D("0.001"), large=D("0.010"), signal=D("0.001"))

    # 1 - (0.001 + 0.001) / 0.010 = 0.8
    assert break_even_escalation_rate(prices) == D("0.8")


def test_at_the_break_even_rate_the_cascade_matches_big_only() -> None:
    prices = TierPrices(small=D("0.002"), large=D("0.010"), signal=D("0.002"))
    rate = break_even_escalation_rate(prices)

    assert savings_per_request(prices, rate) == D("0")
    assert cascade_cost_per_request(prices, rate) == prices.large


def test_a_free_signal_still_pays_for_the_small_attempt() -> None:
    """A signal reusing existing samples is not a cascade with no overhead."""
    prices = TierPrices(small=D("0.004"), large=D("0.010"), signal=D("0"))

    assert prices.overhead == D("0.004")
    assert break_even_escalation_rate(prices) == D("0.6")


def test_overhead_at_or_above_the_large_tier_admits_no_rate() -> None:
    """The ceiling is zero, not negative: no rate makes this cascade cheaper."""
    for small in (D("0.010"), D("0.020")):
        prices = TierPrices(small=small, large=D("0.010"))
        assert break_even_escalation_rate(prices) == D("0")
        assert savings_per_request(prices, D("0")) <= D("0")


def test_zero_overhead_would_be_cheaper_at_every_rate() -> None:
    prices = TierPrices(small=D("0"), large=D("0.010"), signal=D("0"))

    assert break_even_escalation_rate(prices) == D("1")


def test_savings_fall_as_escalation_rises() -> None:
    prices = TierPrices(small=D("0.001"), large=D("0.010"), signal=D("0.001"))
    rates = [D("0.0"), D("0.25"), D("0.5"), D("0.75"), D("1.0")]

    savings = [savings_per_request(prices, rate) for rate in rates]

    assert savings == sorted(savings, reverse=True)
    assert savings[0] > D("0")
    assert savings[-1] < D("0")


def test_quality_condition_ignores_the_escalation_rate() -> None:
    """Cascade quality >= big-only reduces to retained >= large-tier quality."""
    assert quality_condition_holds(D("0.90"), D("0.90"))
    assert quality_condition_holds(D("0.95"), D("0.90"))
    assert not quality_condition_holds(D("0.89"), D("0.90"))


def test_invalid_prices_and_rates_are_rejected() -> None:
    with pytest.raises(ValueError, match="large cost must be positive"):
        TierPrices(small=D("0.001"), large=D("0"))
    with pytest.raises(ValueError, match="small cost"):
        TierPrices(small=D("-0.001"), large=D("0.010"))
    with pytest.raises(ValueError, match="signal cost"):
        TierPrices(small=D("0.001"), large=D("0.010"), signal=D("-1"))

    prices = TierPrices(small=D("0.001"), large=D("0.010"))
    with pytest.raises(ValueError, match="escalation rate"):
        cascade_cost_per_request(prices, D("1.5"))
    with pytest.raises(ValueError, match="escalation rate"):
        cascade_cost_per_request(prices, D("-0.1"))

    with pytest.raises(ValueError, match="retained quality"):
        quality_condition_holds(D("1.5"), D("0.9"))


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        ("0.5", "verdict: cheaper than big-only by 0.003 per request"),
        ("0.8", "verdict: exactly break-even with big-only, before fixed costs"),
        ("0.9", "verdict: more expensive than big-only by 0.001 per request"),
    ],
)
def test_cli_reports_a_verdict_against_the_break_even_rate(
    rate: str, expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "--small-cost",
            "0.001",
            "--large-cost",
            "0.010",
            "--signal-cost",
            "0.001",
            "--escalation-rate",
            rate,
        ]
    )

    assert exit_code == 0
    lines = capsys.readouterr().out.splitlines()
    assert "break-even escalation rate: 0.8000" in lines
    assert expected in lines


def test_cli_reports_when_no_rate_can_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--small-cost", "0.02", "--large-cost", "0.01"]) == 0

    out = capsys.readouterr().out
    assert "break-even escalation rate: 0.0000" in out
    assert "no escalation rate is cheaper than big-only" in out


def test_cli_rejects_a_free_large_tier_as_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--small-cost", "0.001", "--large-cost", "0"])

    assert raised.value.code == 2
    assert "large cost must be positive" in capsys.readouterr().err


def test_amount_formatting_strips_scale_without_going_exponential() -> None:
    """Decimal keeps scale through arithmetic; display should not inherit it."""
    assert format_amount(D("0.0030")) == "0.003"
    assert format_amount(D("0.001")) == "0.001"
    assert format_amount(D("0")) == "0"
    # normalize() alone would render this as 1E+2.
    assert format_amount(D("100")) == "100"
    assert format_amount(D("1.500")) == "1.5"


def test_readme_example_output_is_reproduced_exactly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The README quotes this run; drift between them is a documentation bug."""
    readme = (ROOT / "README.md").read_text()
    blocks = [
        block
        for block in re.findall(r"```text\n(.*?)```", readme, re.DOTALL)
        if "break-even escalation rate:" in block
    ]
    assert len(blocks) == 1

    assert (
        main(
            [
                "--small-cost",
                "0.001",
                "--large-cost",
                "0.010",
                "--signal-cost",
                "0.001",
                "--escalation-rate",
                "0.9",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out == blocks[0]
