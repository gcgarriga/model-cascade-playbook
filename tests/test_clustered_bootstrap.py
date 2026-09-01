from __future__ import annotations

from collections.abc import Sequence

import pytest

from examples.clustered_bootstrap import (
    Interval,
    bootstrap_ci,
    naive_bootstrap_ci,
)


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean of an empty sample is undefined")
    return sum(values) / len(values)


def perfectly_clustered() -> list[list[int]]:
    """100 problems x 3 samples, where a problem's samples always agree.

    The extreme of clustering, and close to what k=3 sampling produces when
    task difficulty dominates sampling noise.
    """
    return [[1, 1, 1] if index < 25 else [0, 0, 0] for index in range(100)]


def test_clustered_interval_is_wider_than_ignoring_the_clustering() -> None:
    """The whole reason to resample clusters.

    With three perfectly correlated samples per problem, resampling
    observations pretends there are 300 independent draws when there are 100.
    The interval should be about sqrt(3) times too narrow.
    """
    clusters = perfectly_clustered()

    clustered = bootstrap_ci(clusters, mean, replicates=2000, seed=44)
    naive = naive_bootstrap_ci(clusters, mean, replicates=2000, seed=44)

    assert clustered.estimate == naive.estimate == 0.25
    clustered_width = clustered.high - clustered.low
    naive_width = naive.high - naive.low
    assert clustered_width > naive_width
    assert 1.5 < clustered_width / naive_width < 2.0


def test_interval_brackets_its_own_estimate() -> None:
    clusters = perfectly_clustered()

    interval = bootstrap_ci(clusters, mean, replicates=500, seed=1)

    assert interval.low <= interval.estimate <= interval.high
    assert interval.clusters == 100
    assert interval.confidence == 0.95


def test_results_are_reproducible_from_the_seed() -> None:
    clusters = perfectly_clustered()

    first = bootstrap_ci(clusters, mean, replicates=500, seed=7)
    second = bootstrap_ci(clusters, mean, replicates=500, seed=7)
    different = bootstrap_ci(clusters, mean, replicates=500, seed=8)

    assert first == second
    assert (different.low, different.high) != (first.low, first.high)


def test_statistic_receives_flat_observations_not_the_grouping() -> None:
    """Clustering governs resampling only; the statistic never sees groups."""
    seen: list[int] = []

    def recording_mean(values: Sequence[int]) -> float:
        seen.append(len(values))
        return mean(values)

    bootstrap_ci(
        [[1, 1, 1], [0, 0, 0], [1, 0, 1]],
        recording_mean,
        replicates=5,
        seed=0,
    )

    # Nine observations on the full data and on every resample; the jackknife
    # folds see six because one cluster of three is held out.
    assert set(seen) == {9, 6}


def test_bca_and_percentile_agree_on_symmetric_data() -> None:
    """Bias correction should barely move a symmetric replicate distribution."""
    clusters = [[value, value] for value in range(-20, 21)]

    bca = bootstrap_ci(clusters, mean, replicates=1500, seed=3, method="bca")
    percentile = bootstrap_ci(
        clusters, mean, replicates=1500, seed=3, method="percentile"
    )

    assert bca.method_used == "bca"
    assert percentile.method_used == "percentile"
    bca_width = bca.high - bca.low
    percentile_width = percentile.high - percentile.low
    assert abs(bca_width - percentile_width) / percentile_width < 0.25


def test_bca_falls_back_and_says_so_when_it_degenerates() -> None:
    """A constant statistic gives BCa no spread to correct against.

    Silently returning a percentile interval labelled BCa would misreport the
    method; the fallback is visible in `method_used`.
    """
    clusters = [[1, 1], [1, 1], [1, 1], [1, 1]]

    interval = bootstrap_ci(clusters, mean, replicates=200, seed=0, method="bca")

    assert interval.method_used == "percentile"
    assert interval.low == interval.high == 1.0


def test_replicates_that_leave_the_statistic_undefined_are_dropped() -> None:
    """A resample can omit a class; the survivor count stays visible."""

    def only_mixed(values: Sequence[int]) -> float:
        if len(set(values)) < 2:
            raise ValueError("needs both classes")
        return mean(values)

    interval = bootstrap_ci(
        [[1], [0]],
        only_mixed,
        replicates=200,
        seed=0,
    )

    # Resamples drawing the same cluster twice are undefined and dropped, so
    # fewer replicates survive than were requested.
    assert 0 < interval.replicates < 200


def test_invalid_inputs_are_rejected() -> None:
    clusters = perfectly_clustered()

    with pytest.raises(ValueError, match="at least two clusters"):
        bootstrap_ci([[1, 1]], mean)
    with pytest.raises(ValueError, match="confidence must be"):
        bootstrap_ci(clusters, mean, confidence=1.0)
    with pytest.raises(ValueError, match="confidence must be"):
        bootstrap_ci(clusters, mean, confidence=0.0)
    with pytest.raises(ValueError, match="replicates must be positive"):
        bootstrap_ci(clusters, mean, replicates=0)
    with pytest.raises(ValueError, match="at least two observations"):
        naive_bootstrap_ci([[1]], mean)


def test_a_statistic_broken_on_the_full_data_raises_its_own_error() -> None:
    """Clearer than reporting it as a resampling failure."""

    def always_fails(values: Sequence[int]) -> float:
        raise ValueError("never defined")

    with pytest.raises(ValueError, match="never defined"):
        bootstrap_ci([[1], [0]], always_fails, replicates=10, seed=0)


def test_every_resample_undefined_is_an_error_not_a_silent_empty_interval() -> None:
    """Defined on the full data, undefined on every resample.

    Twenty singleton clusters drawn with replacement repeat a cluster with
    probability 1 - 20!/20**20, so no resample keeps all twenty distinct.
    """

    def needs_every_cluster(values: Sequence[int]) -> float:
        if len(set(values)) < 20:
            raise ValueError("needs all twenty distinct")
        return mean(values)

    clusters = [[index] for index in range(20)]
    assert needs_every_cluster([index for index in range(20)]) == 9.5

    with pytest.raises(ValueError, match="every resample"):
        bootstrap_ci(clusters, needs_every_cluster, replicates=50, seed=0)


def test_excludes_reports_whether_a_reference_value_is_outside() -> None:
    interval = Interval(
        estimate=0.25,
        low=0.16,
        high=0.33,
        confidence=0.95,
        replicates=2000,
        clusters=100,
        method_used="bca",
    )

    assert interval.excludes(0.0)
    assert interval.excludes(0.5)
    assert not interval.excludes(0.25)
    assert not interval.excludes(0.16)


def test_documented_output_is_reproduced_exactly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`docs/concepts/evaluation.md` quotes this run; drift is a doc bug."""
    import re

    from examples.clustered_bootstrap import main
    from tests.support import ROOT

    chapter = (ROOT / "docs/concepts/evaluation.md").read_text()
    blocks = [
        block
        for block in re.findall(r"```text\n(.*?)```", chapter, re.DOTALL)
        if "by problem (correct)" in block
    ]
    assert len(blocks) == 1

    assert main([]) == 0

    assert capsys.readouterr().out == blocks[0]
