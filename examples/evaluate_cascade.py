"""Evaluate simple cascade policies on a deterministic synthetic workload."""

from __future__ import annotations

import argparse
import csv
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from examples.cascade_costs import (
    ZERO,
    CostBreakdown,
    PricedUsage,
    TokenRates,
    TokenUsage,
    require_nonnegative,
)


@dataclass(frozen=True)
class Score:
    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.value) or not 0 <= self.value <= 1:
            raise ValueError("score must be finite and between 0 and 1")


class SignalIssue(StrEnum):
    MISSING = "missing"
    MALFORMED = "malformed"


def parse_score(raw: str | None) -> Score | SignalIssue:
    if raw is None:
        return SignalIssue.MISSING
    try:
        value = float(raw)
    except ValueError:
        return SignalIssue.MALFORMED
    try:
        return Score(value)
    except ValueError:
        return SignalIssue.MALFORMED


@dataclass(frozen=True)
class Case:
    case_id: str
    small_correct: bool
    big_correct: bool
    signal: Score | SignalIssue
    small: PricedUsage
    big: PricedUsage
    signal_cost: Decimal = ZERO

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case ID must not be empty")
        require_nonnegative(self.signal_cost, "signal cost")


@dataclass(frozen=True)
class CostModel:
    small_fixed: Decimal = ZERO
    big_fixed: Decimal = ZERO

    def __post_init__(self) -> None:
        require_nonnegative(self.small_fixed, "small fixed cost")
        require_nonnegative(self.big_fixed, "big fixed cost")


class Policy(StrEnum):
    SMALL_ONLY = "small-only"
    BIG_ONLY = "big-only"
    THRESHOLD = "threshold"


@dataclass(frozen=True)
class Evaluation:
    policy: Policy
    cases: int
    correct: int
    escalated: int
    retained_failures: int
    recovered_failures: int
    costs: CostBreakdown

    @property
    def quality(self) -> Decimal:
        return Decimal(self.correct) / Decimal(self.cases)

    @property
    def escalation_rate(self) -> Decimal:
        return Decimal(self.escalated) / Decimal(self.cases)


def _must_escalate(signal: Score | SignalIssue, threshold: Score) -> bool:
    return isinstance(signal, SignalIssue) or signal.value < threshold.value


def evaluate(
    cases: Sequence[Case],
    policy: Policy,
    model: CostModel,
    *,
    threshold: Score | None = None,
) -> Evaluation:
    if not cases:
        raise ValueError("at least one case is required")
    identifiers = [item.case_id for item in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("case IDs must be unique")

    correct = escalated = retained_failures = recovered_failures = 0
    signal_cost = variable_cost = ZERO
    reasoning_included = True

    for item in cases:
        if policy is Policy.SMALL_ONLY:
            selected_correct = item.small_correct
            variable_cost += item.small.variable_cost
            reasoning_included &= item.small.reasoning_included
            retained_failures += int(not item.small_correct)
        elif policy is Policy.BIG_ONLY:
            selected_correct = item.big_correct
            variable_cost += item.big.variable_cost
            reasoning_included &= item.big.reasoning_included
        else:
            if threshold is None:
                raise ValueError("threshold policy requires a threshold")
            route_to_big = _must_escalate(item.signal, threshold)
            escalated += int(route_to_big)
            signal_cost += item.signal_cost
            variable_cost += item.small.variable_cost
            reasoning_included &= item.small.reasoning_included
            if route_to_big:
                selected_correct = item.big_correct
                variable_cost += item.big.variable_cost
                reasoning_included &= item.big.reasoning_included
                recovered_failures += int(not item.small_correct and item.big_correct)
            else:
                selected_correct = item.small_correct
                retained_failures += int(not item.small_correct)
        correct += int(selected_correct)

    fixed = {
        Policy.SMALL_ONLY: model.small_fixed,
        Policy.BIG_ONLY: model.big_fixed,
        Policy.THRESHOLD: model.small_fixed + model.big_fixed,
    }[policy]
    return Evaluation(
        policy=policy,
        cases=len(cases),
        correct=correct,
        escalated=escalated,
        retained_failures=retained_failures,
        recovered_failures=recovered_failures,
        costs=CostBreakdown(
            signal=signal_cost,
            variable=variable_cost,
            fixed=fixed,
            reasoning_included=reasoning_included,
        ),
    )


def pareto_frontier(results: Sequence[Evaluation]) -> tuple[Evaluation, ...]:
    def dominates(left: Evaluation, right: Evaluation) -> bool:
        no_worse = (
            left.quality >= right.quality and left.costs.total <= right.costs.total
        )
        strictly_better = (
            left.quality > right.quality or left.costs.total < right.costs.total
        )
        return no_worse and strictly_better

    return tuple(
        candidate
        for index, candidate in enumerate(results)
        if not any(
            dominates(other, candidate)
            for other_index, other in enumerate(results)
            if other_index != index
        )
    )


def reasoning_status(result: Evaluation) -> str:
    return "included" if result.costs.reasoning_included else "unknown"


@dataclass(frozen=True)
class Scenario:
    """A named workload plus the cost model it is evaluated under."""

    name: str
    cases: tuple[Case, ...]
    model: CostModel
    note: str


def _priced_rows(
    rows: Sequence[tuple[str, bool, bool, str | None, int, int]],
    *,
    small_rates: TokenRates,
    big_rates: TokenRates,
    signal_cost: Decimal,
) -> tuple[Case, ...]:
    return tuple(
        Case(
            case_id=case_id,
            small_correct=small_correct,
            big_correct=big_correct,
            signal=parse_score(raw_score),
            small=small_rates.price(
                TokenUsage(input_tokens, output_tokens, reasoning_tokens=0)
            ),
            big=big_rates.price(
                TokenUsage(input_tokens, output_tokens, reasoning_tokens=None)
            ),
            signal_cost=signal_cost,
        )
        for (
            case_id,
            small_correct,
            big_correct,
            raw_score,
            input_tokens,
            output_tokens,
        ) in rows
    )


def unfavorable_scenario() -> Scenario:
    """Four cases where routing loses to a plain baseline.

    The signal routes correctly, yet the cascade still reaches big-only quality
    at a higher total cost: it provisions both tiers, and on this tiny workload
    the two fixed charges swamp the per-request saving.
    """
    small_rates = TokenRates(
        Decimal("0.0001"),
        Decimal("0.0002"),
        reasoning_per_token=ZERO,
    )
    big_rates = TokenRates(Decimal("0.0004"), Decimal("0.0008"))
    rows = (
        ("clear", True, True, "0.90", 80, 20),
        ("recoverable", False, True, "0.20", 90, 25),
        ("missing", False, True, None, 70, 20),
        ("hard", False, False, "invalid", 100, 30),
    )
    cases = _priced_rows(
        rows,
        small_rates=small_rates,
        big_rates=big_rates,
        signal_cost=Decimal("0.003"),
    )
    return Scenario(
        name="unfavorable",
        cases=cases,
        model=CostModel(small_fixed=Decimal("0.500"), big_fixed=Decimal("1.500")),
        note="fixed costs dominate a four-case workload",
    )


def favorable_scenario() -> Scenario:
    """Twenty cases where routing earns its place.

    Same structure, three things changed: enough requests for the fixed charges
    to amortize, a wider gap between tier prices, and a signal that keeps the
    answers worth keeping. The cascade then matches big-only quality for less.
    """
    small_rates = TokenRates(
        Decimal("0.0001"),
        Decimal("0.0002"),
        reasoning_per_token=ZERO,
    )
    big_rates = TokenRates(Decimal("0.0008"), Decimal("0.0016"))
    rows: list[tuple[str, bool, bool, str | None, int, int]] = [
        (f"retain-{index:02d}", True, True, "0.90", 80, 20) for index in range(15)
    ]
    rows.extend(
        (f"recover-{index:02d}", False, True, "0.20", 80, 20) for index in range(4)
    )
    rows.append(("beyond-both", False, False, "0.10", 80, 20))
    cases = _priced_rows(
        rows,
        small_rates=small_rates,
        big_rates=big_rates,
        signal_cost=Decimal("0.002"),
    )
    return Scenario(
        name="favorable",
        cases=cases,
        model=CostModel(small_fixed=Decimal("0.500"), big_fixed=Decimal("1.500")),
        note="twenty cases, an eightfold price gap, and a signal that discriminates",
    )


SCENARIOS = {
    "unfavorable": unfavorable_scenario,
    "favorable": favorable_scenario,
}

CASE_COLUMNS = (
    "case_id",
    "small_correct",
    "big_correct",
    "signal",
    "small_cost",
    "big_cost",
    "signal_cost",
)


def _parse_bool(raw: str, column: str, case_id: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{case_id}: {column} must be true or false, got {raw!r}")


def _reasoning_included(row: dict[str, str | None], tier: str, case_id: str) -> bool:
    tier_column = f"{tier}_reasoning_included"
    tier_value = row.get(tier_column)
    fallback_value = row.get("reasoning_included")
    if tier_value and tier_value.strip():
        return _parse_bool(tier_value.strip(), tier_column, case_id)
    return _parse_bool(
        (fallback_value or "false").strip(),
        "reasoning_included",
        case_id,
    )


def load_cases(path: Path) -> tuple[Case, ...]:
    """Read a workload from CSV so the comparison can run on your own numbers.

    Required columns are `CASE_COLUMNS`. An empty `signal` cell is a missing
    signal and anything unparseable is a malformed one -- both escalate, and
    both still pay `signal_cost`, because the system already tried to obtain
    them. Optional `small_reasoning_included` and `big_reasoning_included`
    columns mark each tier's cost as complete. The legacy `reasoning_included`
    column applies to both tiers. Omitted values default to false so unknown
    reasoning usage stays visible rather than being quietly counted as zero.
    """
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: no header row")
        missing = [name for name in CASE_COLUMNS if name not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing columns {', '.join(missing)}")
        rows = list(reader)

    if not rows:
        raise ValueError(f"{path}: no case rows")

    cases: list[Case] = []
    for row in rows:
        case_id = (row["case_id"] or "").strip()
        raw_signal = (row["signal"] or "").strip()
        small_correct = _parse_bool(row["small_correct"], "small_correct", case_id)
        big_correct = _parse_bool(row["big_correct"], "big_correct", case_id)
        cases.append(
            Case(
                case_id=case_id,
                small_correct=small_correct,
                big_correct=big_correct,
                signal=parse_score(raw_signal or None),
                small=PricedUsage(
                    Decimal(row["small_cost"]),
                    reasoning_included=_reasoning_included(row, "small", case_id),
                ),
                big=PricedUsage(
                    Decimal(row["big_cost"]),
                    reasoning_included=_reasoning_included(row, "big", case_id),
                ),
                signal_cost=Decimal(row["signal_cost"]),
            )
        )
    return tuple(cases)


def sweep_thresholds(
    cases: Sequence[Case],
    model: CostModel,
    thresholds: Sequence[Score],
) -> tuple[tuple[Score, Evaluation], ...]:
    """Evaluate threshold routing across cut points.

    One operating point says nothing about whether a threshold is a good one.
    The sweep shows the quality and cost the policy reaches as the cut point
    moves, which is the shape a calibration set is supposed to reveal.
    """
    return tuple(
        (
            threshold,
            evaluate(cases, Policy.THRESHOLD, model, threshold=threshold),
        )
        for threshold in thresholds
    )


def default_sweep_points() -> tuple[Score, ...]:
    return tuple(Score(value / 10) for value in range(11))


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.001'))}"


@dataclass(frozen=True)
class Column:
    """One report column: its heading, width, and how to render a row.

    Header and row were previously two parallel format strings, so a width
    changed in one place silently misaligned the other.
    """

    header: str
    width: int
    render: Callable[[Evaluation], str]


POLICY_COLUMNS: dict[str, Column] = {
    "policy": Column("policy", -12, lambda result: result.policy.value),
    "quality": Column("quality", 7, lambda result: _format_decimal(result.quality)),
    "escalation_rate": Column(
        "escalation_rate",
        15,
        lambda result: _format_decimal(result.escalation_rate),
    ),
    "retained_failures": Column(
        "retained_failures",
        17,
        lambda result: str(result.retained_failures),
    ),
    "recovered_failures": Column(
        "recovered_failures",
        18,
        lambda result: str(result.recovered_failures),
    ),
    "signal": Column("signal", 6, lambda result: _format_decimal(result.costs.signal)),
    "variable": Column(
        "variable", 8, lambda result: _format_decimal(result.costs.variable)
    ),
    "fixed": Column("fixed", 5, lambda result: _format_decimal(result.costs.fixed)),
    "total": Column("total", 5, lambda result: _format_decimal(result.costs.total)),
    "reasoning": Column("reasoning", 9, reasoning_status),
}


def _cell(text: str, width: int) -> str:
    """Negative widths are left-aligned; positive widths right-aligned."""
    return f"{text:<{-width}}" if width < 0 else f"{text:>{width}}"


def _render_table(columns: Sequence[Column], rows: Sequence[Evaluation]) -> list[str]:
    lines = [" ".join(_cell(column.header, column.width) for column in columns)]
    lines.extend(
        " ".join(_cell(column.render(row), column.width) for column in columns)
        for row in rows
    )
    return lines


def _print_policy_table(results: Sequence[Evaluation]) -> None:
    for line in _render_table(tuple(POLICY_COLUMNS.values()), results):
        print(line)
    print(
        "pareto policies: "
        + ", ".join(result.policy.value for result in pareto_frontier(results))
    )


def _print_sweep(sweep: Sequence[tuple[Score, Evaluation]]) -> None:
    columns = tuple(
        replace(POLICY_COLUMNS[key], width=7) if key == "total" else POLICY_COLUMNS[key]
        for key in (
            "quality",
            "escalation_rate",
            "retained_failures",
            "recovered_failures",
            "total",
        )
    )
    headers = [_cell("threshold", 9)]
    headers.extend(_cell(column.header, column.width) for column in columns)
    print(" ".join(headers))
    for threshold, result in sweep:
        cells = [_cell(_format_decimal(Decimal(str(threshold.value))), 9)]
        cells.extend(_cell(column.render(result), column.width) for column in columns)
        print(" ".join(cells))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare simple cascade policies on a synthetic workload."
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default="unfavorable",
        help=(
            "Built-in workload to evaluate (default: unfavorable, where routing "
            "loses to a plain baseline)."
        ),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=None,
        help=(
            "CSV workload to evaluate instead of a built-in scenario. Columns: "
            + ", ".join(CASE_COLUMNS)
            + ". Optional reasoning columns: small_reasoning_included, "
            "big_reasoning_included."
        ),
    )
    parser.add_argument(
        "--small-fixed",
        type=Decimal,
        default=None,
        help="Fixed cost of provisioning the small tier (default: scenario value).",
    )
    parser.add_argument(
        "--big-fixed",
        type=Decimal,
        default=None,
        help="Fixed cost of provisioning the large tier (default: scenario value).",
    )
    parser.add_argument(
        "--threshold",
        type=Decimal,
        default=Decimal("0.7"),
        help="Cut point for the threshold policy (default: 0.7).",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Also print threshold routing across cut points from 0.0 to 1.0.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.cases is not None:
            cases = load_cases(args.cases)
            model = CostModel()
        else:
            scenario = SCENARIOS[args.scenario]()
            cases = scenario.cases
            model = scenario.model
        if args.small_fixed is not None or args.big_fixed is not None:
            model = CostModel(
                small_fixed=(
                    model.small_fixed if args.small_fixed is None else args.small_fixed
                ),
                big_fixed=(
                    model.big_fixed if args.big_fixed is None else args.big_fixed
                ),
            )
        threshold = Score(float(args.threshold))
        results = tuple(
            evaluate(
                cases,
                policy,
                model,
                threshold=threshold if policy is Policy.THRESHOLD else None,
            )
            for policy in Policy
        )
        sweep = (
            sweep_thresholds(cases, model, default_sweep_points()) if args.sweep else ()
        )
    except (OSError, ValueError, ArithmeticError) as error:
        parser.error(str(error))

    _print_policy_table(results)
    if sweep:
        print()
        _print_sweep(sweep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
