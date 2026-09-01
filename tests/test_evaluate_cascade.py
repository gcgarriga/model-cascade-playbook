from __future__ import annotations

import math
import re
from decimal import Decimal
from pathlib import Path

import pytest

from examples.cascade_costs import PricedUsage, TokenRates, TokenUsage
from examples.evaluate_cascade import (
    Case,
    CostModel,
    Policy,
    Score,
    SignalIssue,
    default_sweep_points,
    evaluate,
    favorable_scenario,
    load_cases,
    main,
    pareto_frontier,
    parse_score,
    reasoning_status,
    sweep_thresholds,
    unfavorable_scenario,
)

D = Decimal


def case(
    case_id: str,
    *,
    small_correct: bool,
    big_correct: bool,
    signal: Score | SignalIssue,
    small_cost: str = "0.10",
    big_cost: str = "0.80",
    signal_cost: str = "0.05",
    small_reasoning_included: bool = True,
) -> Case:
    return Case(
        case_id=case_id,
        small_correct=small_correct,
        big_correct=big_correct,
        signal=signal,
        small=PricedUsage(
            D(small_cost),
            reasoning_included=small_reasoning_included,
        ),
        big=PricedUsage(D(big_cost), reasoning_included=False),
        signal_cost=D(signal_cost),
    )


def test_score_and_cost_invariants_reject_invalid_values() -> None:
    for score_value in (math.nan, math.inf, -0.01, 1.01):
        with pytest.raises(ValueError):
            Score(score_value)

    for cost_value in (D("-0.01"), D("Infinity"), D("NaN")):
        with pytest.raises(ValueError):
            PricedUsage(cost_value, reasoning_included=True)

    with pytest.raises(ValueError):
        TokenUsage(input_tokens=-1, output_tokens=0)
    with pytest.raises(ValueError):
        TokenUsage(input_tokens=0, output_tokens=-1)
    with pytest.raises(ValueError):
        TokenUsage(input_tokens=0, output_tokens=0, reasoning_tokens=-1)

    with pytest.raises(ValueError):
        TokenRates(input_per_token=D("-0.001"), output_per_token=D("0.002"))
    with pytest.raises(ValueError):
        TokenRates(input_per_token=D("0.001"), output_per_token=D("-0.002"))
    with pytest.raises(ValueError):
        TokenRates(
            input_per_token=D("0.001"),
            output_per_token=D("0.002"),
            reasoning_per_token=D("NaN"),
        )

    with pytest.raises(ValueError):
        CostModel(small_fixed=D("-1"))
    with pytest.raises(ValueError):
        CostModel(big_fixed=D("Infinity"))

    with pytest.raises(ValueError):
        case(
            "bad-cost",
            small_correct=True,
            big_correct=True,
            signal=Score(0.9),
            signal_cost="-0.01",
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, SignalIssue.MISSING),
        ("not-a-number", SignalIssue.MALFORMED),
        ("nan", SignalIssue.MALFORMED),
        ("1.1", SignalIssue.MALFORMED),
        ("0.75", Score(0.75)),
    ],
)
def test_score_parser_is_strict_and_fail_closed(
    raw: str | None, expected: Score | SignalIssue
) -> None:
    assert parse_score(raw) == expected


def test_duplicate_case_ids_are_rejected() -> None:
    duplicate = case(
        "same",
        small_correct=True,
        big_correct=True,
        signal=Score(0.9),
    )

    with pytest.raises(ValueError, match="case IDs must be unique"):
        evaluate(
            (duplicate, duplicate),
            Policy.THRESHOLD,
            CostModel(),
            threshold=Score(0.7),
        )


def test_blank_case_id_and_empty_workload_are_rejected() -> None:
    with pytest.raises(ValueError, match="case ID must not be empty"):
        case(
            "   ",
            small_correct=True,
            big_correct=True,
            signal=Score(0.9),
        )

    with pytest.raises(ValueError, match="at least one case"):
        evaluate((), Policy.SMALL_ONLY, CostModel())

    with pytest.raises(ValueError, match="requires a threshold"):
        evaluate(
            (
                case(
                    "missing-threshold",
                    small_correct=True,
                    big_correct=True,
                    signal=Score(0.9),
                ),
            ),
            Policy.THRESHOLD,
            CostModel(),
        )


def test_threshold_boundary_retains_at_threshold_and_escalates_below() -> None:
    at_threshold = case(
        "at",
        small_correct=True,
        big_correct=True,
        signal=Score(0.7),
    )
    below_threshold = case(
        "below",
        small_correct=True,
        big_correct=True,
        signal=Score(0.699),
    )
    model = CostModel()

    assert (
        evaluate(
            (at_threshold,),
            Policy.THRESHOLD,
            model,
            threshold=Score(0.7),
        ).escalated
        == 0
    )
    below_result = evaluate(
        (below_threshold,),
        Policy.THRESHOLD,
        model,
        threshold=Score(0.7),
    )
    assert below_result.escalated == 1
    assert below_result.recovered_failures == 0


def test_threshold_policy_counts_outcomes_and_exact_costs() -> None:
    cases = (
        case("retain-good", small_correct=True, big_correct=True, signal=Score(0.9)),
        case("retain-bad", small_correct=False, big_correct=True, signal=Score(0.8)),
        case("recover", small_correct=False, big_correct=True, signal=Score(0.2)),
        case("remain-bad", small_correct=False, big_correct=False, signal=Score(0.1)),
    )
    model = CostModel(
        small_fixed=D("1.25"),
        big_fixed=D("2.50"),
    )

    result = evaluate(cases, Policy.THRESHOLD, model, threshold=Score(0.7))

    assert result.correct == 2
    assert result.quality == D("0.5")
    assert result.escalated == 2
    assert result.escalation_rate == D("0.5")
    assert result.retained_failures == 1
    assert result.recovered_failures == 1
    assert result.costs.signal == D("0.20")
    assert result.costs.variable == D("2.00")
    assert result.costs.fixed == D("3.75")
    assert result.costs.total == D("5.95")
    assert result.costs.reasoning_included is False


def test_threshold_policy_provisions_both_tiers_when_all_cases_are_retained() -> None:
    item = case(
        "retained",
        small_correct=True,
        big_correct=True,
        signal=Score(0.9),
        small_cost="0.12",
        big_cost="0.80",
    )
    model = CostModel(
        small_fixed=D("1.00"),
        big_fixed=D("2.00"),
    )

    result = evaluate(
        (item,),
        Policy.THRESHOLD,
        model,
        threshold=Score(0.7),
    )

    assert result.escalated == 0
    assert result.costs.fixed == D("3.00")
    assert result.costs.variable == D("0.12")


@pytest.mark.parametrize("issue", [SignalIssue.MISSING, SignalIssue.MALFORMED])
def test_missing_or_malformed_signal_escalates_and_still_costs(
    issue: SignalIssue,
) -> None:
    item = case(
        "uncertain",
        small_correct=False,
        big_correct=True,
        signal=issue,
        signal_cost="0.07",
    )

    result = evaluate(
        (item,),
        Policy.THRESHOLD,
        CostModel(),
        threshold=Score(0.7),
    )

    assert result.escalated == 1
    assert result.recovered_failures == 1
    assert result.costs.signal == D("0.07")


def test_small_only_and_big_only_charge_only_their_own_tiers() -> None:
    item = case(
        "one",
        small_correct=False,
        big_correct=True,
        signal=Score(0.5),
        small_cost="0.11",
        big_cost="0.83",
        signal_cost="0.09",
    )
    model = CostModel(
        small_fixed=D("1.20"),
        big_fixed=D("2.30"),
    )

    small = evaluate((item,), Policy.SMALL_ONLY, model)
    big = evaluate((item,), Policy.BIG_ONLY, model)

    assert small.costs.total == D("1.31")
    assert small.costs.signal == D("0")
    assert big.costs.total == D("3.13")
    assert big.costs.signal == D("0")
    assert big.costs.variable == D("0.83")
    assert big.escalation_rate == D("0")


def test_zero_variable_cost_can_still_have_fixed_cost() -> None:
    item = case(
        "local",
        small_correct=True,
        big_correct=True,
        signal=Score(0.9),
        small_cost="0",
    )

    result = evaluate(
        (item,),
        Policy.SMALL_ONLY,
        CostModel(small_fixed=D("4.00")),
    )

    assert result.costs.variable == D("0")
    assert result.costs.total == D("4.00")


def test_token_costs_are_exact_and_unknown_reasoning_stays_unknown() -> None:
    rates = TokenRates(
        input_per_token=D("0.0002"),
        output_per_token=D("0.0005"),
        reasoning_per_token=D("0.001"),
    )

    known = rates.price(
        TokenUsage(input_tokens=10, output_tokens=4, reasoning_tokens=3)
    )
    unknown = rates.price(
        TokenUsage(input_tokens=10, output_tokens=4, reasoning_tokens=None)
    )
    missing_rate = TokenRates(
        input_per_token=D("0.0002"),
        output_per_token=D("0.0005"),
        reasoning_per_token=None,
    ).price(TokenUsage(input_tokens=10, output_tokens=4, reasoning_tokens=3))

    assert known == PricedUsage(D("0.0070"), reasoning_included=True)
    assert unknown == PricedUsage(D("0.0040"), reasoning_included=False)
    assert missing_rate == PricedUsage(D("0.0040"), reasoning_included=False)


def test_pareto_frontier_keeps_exact_ties() -> None:
    item = case("one", small_correct=True, big_correct=True, signal=Score(0.9))
    model = CostModel()
    first = evaluate((item,), Policy.SMALL_ONLY, model)
    tie = evaluate((item,), Policy.SMALL_ONLY, model)
    dominated = evaluate((item,), Policy.BIG_ONLY, model)

    assert pareto_frontier((first, tie, dominated)) == (first, tie)


def test_reasoning_status_is_derived_from_evaluated_costs() -> None:
    item = case("known", small_correct=True, big_correct=True, signal=Score(0.9))
    known = evaluate(
        (item,),
        Policy.SMALL_ONLY,
        CostModel(),
    )
    unknown = evaluate(
        (item,),
        Policy.BIG_ONLY,
        CostModel(),
    )
    unknown_small = evaluate(
        (
            case(
                "unknown-small",
                small_correct=True,
                big_correct=True,
                signal=Score(0.9),
                small_reasoning_included=False,
            ),
        ),
        Policy.SMALL_ONLY,
        CostModel(),
    )

    assert reasoning_status(known) == "included"
    assert reasoning_status(unknown) == "unknown"
    assert reasoning_status(unknown_small) == "unknown"


def test_cli_output_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text()
    output_blocks = [
        block
        for block in re.findall(r"```text\n(.*?)```", readme, re.DOTALL)
        if "pareto policies:" in block
    ]
    assert len(output_blocks) == 1
    expected = output_blocks[0]

    assert main([]) == 0
    first = capsys.readouterr().out
    assert main([]) == 0
    second = capsys.readouterr().out

    assert first == expected
    assert first == second


def test_cli_rejects_unknown_arguments() -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--unknown"])

    assert raised.value.code == 2


def test_favorable_scenario_puts_routing_on_the_pareto_frontier() -> None:
    """The counterpart to the default: a workload where the cascade wins.

    Shipping only the losing fixture teaches that cascades do not pay, rather
    than what has to be true for them to pay.
    """
    scenario = favorable_scenario()
    results = tuple(
        evaluate(
            scenario.cases,
            policy,
            scenario.model,
            threshold=Score(0.7) if policy is Policy.THRESHOLD else None,
        )
        for policy in Policy
    )
    frontier = {result.policy for result in pareto_frontier(results)}

    assert Policy.THRESHOLD in frontier
    assert Policy.BIG_ONLY not in frontier

    by_policy = {result.policy: result for result in results}
    threshold = by_policy[Policy.THRESHOLD]
    big_only = by_policy[Policy.BIG_ONLY]
    assert threshold.quality == big_only.quality
    assert threshold.costs.total < big_only.costs.total


def test_unfavorable_scenario_still_loses_to_a_plain_baseline() -> None:
    scenario = unfavorable_scenario()
    results = tuple(
        evaluate(
            scenario.cases,
            policy,
            scenario.model,
            threshold=Score(0.7) if policy is Policy.THRESHOLD else None,
        )
        for policy in Policy
    )
    frontier = {result.policy for result in pareto_frontier(results)}

    assert Policy.THRESHOLD not in frontier


def test_sweep_covers_every_cut_point_and_escalation_rises_with_it() -> None:
    scenario = favorable_scenario()
    sweep = sweep_thresholds(scenario.cases, scenario.model, default_sweep_points())

    assert len(sweep) == 11
    assert [threshold.value for threshold, _ in sweep] == [
        value / 10 for value in range(11)
    ]
    rates = [result.escalation_rate for _, result in sweep]
    assert rates == sorted(rates)
    assert rates[0] == D("0")
    assert rates[-1] == D("1")


def test_sweep_exposes_the_plateau_a_coarse_signal_creates() -> None:
    """Distinct cut points are not distinct policies when the score is coarse."""
    scenario = favorable_scenario()
    sweep = sweep_thresholds(scenario.cases, scenario.model, default_sweep_points())
    middle = [result for threshold, result in sweep if 0.3 <= threshold.value <= 0.9]

    assert len({result.costs.total for result in middle}) == 1
    assert len({result.escalation_rate for result in middle}) == 1


def _write_csv(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


VALID_CSV = """case_id,small_correct,big_correct,signal,small_cost,big_cost,signal_cost
a,true,true,0.9,0.01,0.10,0.002
b,false,true,0.2,0.01,0.10,0.002
c,false,true,,0.01,0.10,0.002
d,false,false,junk,0.01,0.10,0.002
"""


def test_csv_workload_round_trips_valid_missing_and_malformed_signals(
    tmp_path: Path,
) -> None:
    cases = load_cases(_write_csv(tmp_path / "w.csv", VALID_CSV))

    assert [item.case_id for item in cases] == ["a", "b", "c", "d"]
    assert cases[0].signal == Score(0.9)
    assert cases[2].signal is SignalIssue.MISSING
    assert cases[3].signal is SignalIssue.MALFORMED
    assert cases[0].small == PricedUsage(D("0.01"), reasoning_included=False)
    assert cases[0].signal_cost == D("0.002")


def test_csv_workload_defaults_reasoning_to_unknown(tmp_path: Path) -> None:
    """Silence about reasoning usage must not be read as zero reasoning usage."""
    cases = load_cases(_write_csv(tmp_path / "w.csv", VALID_CSV))
    result = evaluate(cases, Policy.SMALL_ONLY, CostModel())

    assert reasoning_status(result) == "unknown"


def test_csv_workload_honours_an_explicit_reasoning_column(tmp_path: Path) -> None:
    body = (
        "case_id,small_correct,big_correct,signal,small_cost,big_cost,"
        "signal_cost,reasoning_included\n"
        "a,true,true,0.9,0.01,0.10,0.002,true\n"
    )
    cases = load_cases(_write_csv(tmp_path / "w.csv", body))
    result = evaluate(cases, Policy.SMALL_ONLY, CostModel())

    assert reasoning_status(result) == "included"


def test_csv_workload_tracks_reasoning_per_tier(tmp_path: Path) -> None:
    body = (
        "case_id,small_correct,big_correct,signal,small_cost,big_cost,"
        "signal_cost,small_reasoning_included,big_reasoning_included\n"
        "a,true,true,0.9,0.01,0.10,0.002,true,false\n"
    )
    cases = load_cases(_write_csv(tmp_path / "w.csv", body))

    assert cases[0].small.reasoning_included is True
    assert cases[0].big.reasoning_included is False


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("case_id,small_correct\na,true\n", "missing columns"),
        (
            "case_id,small_correct,big_correct,signal,small_cost,big_cost,signal_cost\n",
            "no case rows",
        ),
        (
            "case_id,small_correct,big_correct,signal,small_cost,big_cost,signal_cost\n"
            "a,maybe,true,0.9,0.01,0.10,0.002\n",
            "must be true or false",
        ),
    ],
)
def test_csv_workload_rejects_malformed_files(
    body: str, message: str, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match=message):
        load_cases(_write_csv(tmp_path / "w.csv", body))


def test_cli_scenario_and_sweep_flags(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--scenario", "favorable", "--sweep"]) == 0
    out = capsys.readouterr().out

    assert "pareto policies: small-only, threshold" in out
    assert "threshold quality escalation_rate" in out
    assert out.count("\n") > 15


def test_cli_reads_a_csv_workload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_csv(tmp_path / "w.csv", VALID_CSV)

    assert main(["--cases", str(path)]) == 0
    out = capsys.readouterr().out
    rows = {line.split()[0]: line.split() for line in out.splitlines()[1:4]}

    # No fixed costs come with a CSV workload, so each total is the sum of the
    # per-request costs the file itself declares.
    assert rows["small-only"][-4:-1] == ["0.040", "0.000", "0.040"]
    assert rows["big-only"][-4:-1] == ["0.400", "0.000", "0.400"]
    assert rows["threshold"][-4:-1] == ["0.340", "0.000", "0.348"]
    assert rows["threshold"][1] == "0.750"
    assert rows["threshold"][2] == "0.750"


def test_cli_overrides_fixed_costs(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--scenario", "favorable", "--big-fixed", "0"]) == 0
    out = capsys.readouterr().out
    big_only = next(line for line in out.splitlines() if line.startswith("big-only"))

    assert big_only.split()[-2] == "1.920"


def test_cli_reports_a_bad_workload_as_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_csv(tmp_path / "w.csv", "case_id\na\n")

    with pytest.raises(SystemExit) as raised:
        main(["--cases", str(path)])

    assert raised.value.code == 2
    stderr = capsys.readouterr().err
    assert "missing columns" in stderr
    assert "Traceback" not in stderr
