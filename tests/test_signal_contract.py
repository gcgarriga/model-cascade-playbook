from __future__ import annotations

import tomllib
from typing import Any

import pytest

from tests.support import ROOT

CONTRACT = ROOT / "examples/signal_contract.toml"

REQUIRED_FIELDS = {
    "signal": ("name", "available_when", "range", "polarity", "aggregation"),
    "policy": (
        "threshold",
        "threshold_chosen_on",
        "missing_policy",
        "malformed_policy",
    ),
    "cost": ("extra_calls", "extra_tokens", "extra_seconds"),
    "validity": (
        "distinct_values_observed",
        "missing_rate",
        "malformed_rate",
        "exposure_split",
    ),
}


@pytest.fixture(scope="module")
def contract() -> dict[str, Any]:
    with CONTRACT.open("rb") as handle:
        loaded: dict[str, Any] = tomllib.load(handle)
    return loaded


def test_contract_template_parses_as_toml(contract: dict[str, Any]) -> None:
    """The template is a file readers load, not prose they retype."""
    assert set(contract) == set(REQUIRED_FIELDS)


def test_contract_template_carries_every_required_field(
    contract: dict[str, Any],
) -> None:
    checked = 0
    for section, fields in REQUIRED_FIELDS.items():
        assert set(contract[section]) == set(fields), section
        for field in fields:
            checked += 1
            assert contract[section][field] is not None, (section, field)
    assert checked == sum(len(fields) for fields in REQUIRED_FIELDS.values())
    assert checked >= 16


def test_contract_threshold_and_rates_are_in_range(contract: dict[str, Any]) -> None:
    assert 0 <= contract["policy"]["threshold"] <= 1
    for field in ("missing_rate", "malformed_rate"):
        assert 0 <= contract["validity"][field] <= 1
    for field in ("extra_calls", "extra_tokens"):
        assert contract["cost"][field] >= 0
    assert contract["cost"]["extra_seconds"] >= 0


def test_contract_states_polarity_unambiguously(contract: dict[str, Any]) -> None:
    """An ambiguous polarity can make a good-looking metric describe the
    opposite of what the policy does."""
    polarity = contract["signal"]["polarity"]
    assert polarity in {"higher means retain", "higher means escalate"} or ":" in (
        polarity
    )


def test_missing_and_malformed_values_are_never_silently_dropped(
    contract: dict[str, Any],
) -> None:
    for field in ("missing_policy", "malformed_policy"):
        policy = contract["policy"][field]
        assert "escalate" in policy, field
        assert "record" in policy, field
