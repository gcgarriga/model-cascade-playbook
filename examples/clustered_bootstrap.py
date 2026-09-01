"""Confidence intervals that resample the independent unit.

Repeated generations from one request share a prompt, a task, and usually a
difficulty. They are clustered observations, not independent new requests.
Resampling them individually treats three samples from 100 problems as 300
independent problems, which makes every interval narrower than the evidence
supports.

This module resamples *clusters*. You group observations by whatever the
independent unit actually is -- problem, user, conversation, repository -- and
the interval widens to match.

Two interval methods are provided. `percentile` takes the empirical quantiles
of the replicate distribution. `bca` additionally corrects for median bias and
for a statistic whose variance changes with its own value, which matters for
bounded, skewed statistics such as AUROC near its ceiling. BCa needs a
jackknife over clusters and degenerates on some inputs; when it cannot be
computed the result says so rather than silently returning something else.

Standard library only. For 2,000 replicates over ~100 clusters this runs in
well under a second.
"""

from __future__ import annotations

import argparse
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Literal, TypeVar

Observation = TypeVar("Observation")
Method = Literal["percentile", "bca"]

_NORMAL = NormalDist()


@dataclass(frozen=True)
class Interval:
    """A point estimate with a confidence interval and the method behind it.

    `method_used` may differ from the method requested: BCa degenerates when
    every replicate lands on one side of the estimate, or when the jackknife
    has no spread. Reporting the fallback keeps the interval honest.
    """

    estimate: float
    low: float
    high: float
    confidence: float
    replicates: int
    clusters: int
    method_used: Method

    @property
    def excludes(self) -> Callable[[float], bool]:
        """Whether a reference value lies outside the interval."""

        def test(value: float) -> bool:
            return value < self.low or value > self.high

        return test


def _flatten(
    clusters: Sequence[Sequence[Observation]],
) -> list[Observation]:
    return [item for cluster in clusters for item in cluster]


def _percentile(ordered: Sequence[float], fraction: float) -> float:
    """Linear-interpolated quantile of an already sorted sequence."""
    if not ordered:
        raise ValueError("no replicates to take a percentile from")
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _acceleration(
    clusters: Sequence[Sequence[Observation]],
    statistic: Callable[[Sequence[Observation]], float],
) -> float | None:
    """Jackknife acceleration over clusters; None when it is undefined."""
    jackknife: list[float] = []
    for index in range(len(clusters)):
        remaining = _flatten(
            [cluster for position, cluster in enumerate(clusters) if position != index]
        )
        try:
            jackknife.append(statistic(remaining))
        except (ValueError, ZeroDivisionError):
            return None

    mean = sum(jackknife) / len(jackknife)
    deviations = [mean - value for value in jackknife]
    squares = sum(value**2 for value in deviations)
    if squares == 0:
        return None
    cubes = sum(value**3 for value in deviations)
    return float(cubes / (6 * squares**1.5))


def bootstrap_ci(
    clusters: Sequence[Sequence[Observation]],
    statistic: Callable[[Sequence[Observation]], float],
    *,
    confidence: float = 0.95,
    replicates: int = 2000,
    seed: int = 0,
    method: Method = "bca",
) -> Interval:
    """Resample whole clusters with replacement and summarize the spread.

    `clusters` groups observations by the independent unit. `statistic` is
    applied to the flattened observations, so it never sees the grouping --
    only the resampling does.

    The seed makes the result reproducible; report it alongside the interval so
    someone else can obtain the same numbers from the same inputs.
    """
    if len(clusters) < 2:
        raise ValueError("at least two clusters are required to resample")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    if replicates < 1:
        raise ValueError("replicates must be positive")

    estimate = statistic(_flatten(clusters))

    rng = random.Random(seed)
    count = len(clusters)
    draws: list[float] = []
    for _ in range(replicates):
        sample = _flatten([clusters[rng.randrange(count)] for _ in range(count)])
        try:
            draws.append(statistic(sample))
        except (ValueError, ZeroDivisionError):
            # A resample can omit a class entirely, leaving the statistic
            # undefined. Dropping the replicate is the conventional handling;
            # it is visible because `replicates` records how many survived.
            continue
    if not draws:
        raise ValueError("every resample left the statistic undefined")
    draws.sort()

    tail = (1 - confidence) / 2
    low_fraction, high_fraction = tail, 1 - tail
    method_used: Method = "percentile"

    if method == "bca":
        below = sum(1 for value in draws if value < estimate)
        acceleration = _acceleration(clusters, statistic)
        if acceleration is not None and 0 < below < len(draws):
            bias = _NORMAL.inv_cdf(below / len(draws))
            adjusted: list[float] = []
            for raw in (tail, 1 - tail):
                z = _NORMAL.inv_cdf(raw)
                denominator = 1 - acceleration * (bias + z)
                if denominator == 0:
                    break
                adjusted.append(_NORMAL.cdf(bias + (bias + z) / denominator))
            if len(adjusted) == 2:
                low_fraction, high_fraction = adjusted
                method_used = "bca"

    return Interval(
        estimate=estimate,
        low=_percentile(draws, low_fraction),
        high=_percentile(draws, high_fraction),
        confidence=confidence,
        replicates=len(draws),
        clusters=count,
        method_used=method_used,
    )


def naive_bootstrap_ci(
    clusters: Sequence[Sequence[Observation]],
    statistic: Callable[[Sequence[Observation]], float],
    *,
    confidence: float = 0.95,
    replicates: int = 2000,
    seed: int = 0,
) -> Interval:
    """Resample individual observations, ignoring the clustering.

    Provided to make the mistake visible, not to be used. On clustered data
    this reports a narrower interval than the evidence supports, because it
    treats every observation as an independent draw. Compare it against
    `bootstrap_ci` on the same data and the gap is the overconfidence.
    """
    observations = _flatten(clusters)
    if len(observations) < 2:
        raise ValueError("at least two observations are required to resample")

    estimate = statistic(observations)
    rng = random.Random(seed)
    total = len(observations)
    draws: list[float] = []
    for _ in range(replicates):
        sample = [observations[rng.randrange(total)] for _ in range(total)]
        try:
            draws.append(statistic(sample))
        except (ValueError, ZeroDivisionError):
            continue
    if not draws:
        raise ValueError("every resample left the statistic undefined")
    draws.sort()

    tail = (1 - confidence) / 2
    return Interval(
        estimate=estimate,
        low=_percentile(draws, tail),
        high=_percentile(draws, 1 - tail),
        confidence=confidence,
        replicates=len(draws),
        clusters=len(clusters),
        method_used="percentile",
    )


def _demonstration_clusters() -> list[list[int]]:
    """100 problems, three samples each, samples within a problem agreeing.

    The extreme of clustering, and close to what `k=3` sampling produces when
    task difficulty dominates sampling noise.
    """
    return [[1, 1, 1] if index < 25 else [0, 0, 0] for index in range(100)]


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean of an empty sample is undefined")
    return sum(values) / len(values)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Show how much narrower a confidence interval looks when repeated "
            "samples from one problem are treated as independent."
        )
    )
    parser.add_argument(
        "--replicates",
        type=int,
        default=2000,
        help="Bootstrap replicates (default: 2000).",
    )
    parser.add_argument("--seed", type=int, default=44, help="Seed (default: 44).")
    args = parser.parse_args(argv)

    clusters = _demonstration_clusters()
    try:
        clustered = bootstrap_ci(
            clusters, _mean, replicates=args.replicates, seed=args.seed
        )
        naive = naive_bootstrap_ci(
            clusters, _mean, replicates=args.replicates, seed=args.seed
        )
    except ValueError as error:
        parser.error(str(error))

    print(f"{len(clusters)} problems x 3 samples, samples agree within a problem")
    print(f"{'resampling':<26} {'estimate':>8} {'95% interval':>20} {'width':>7}")
    for label, interval in (
        ("by problem (correct)", clustered),
        ("by sample (overconfident)", naive),
    ):
        span = f"[{interval.low:.3f}, {interval.high:.3f}]"
        print(
            f"{label:<26} {interval.estimate:>8.3f} {span:>20} "
            f"{interval.high - interval.low:>7.3f}"
        )
    ratio = (clustered.high - clustered.low) / (naive.high - naive.low)
    print(
        f"\nresampling by sample understates the interval {ratio:.2f}x; "
        "with k=3 the ceiling is sqrt(3) = 1.73"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
