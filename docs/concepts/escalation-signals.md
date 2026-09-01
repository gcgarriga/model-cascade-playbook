# Escalation signals

[Home](../../README.md) / Concepts / Escalation signals

An escalation signal is information available to the routing policy at decision
time. It is not automatically a measure of correctness. Before using a signal,
write down its range, polarity, cost, latency, and behavior when unavailable.

## Common signal families

| Family | Example | Extra work | Main caution |
| --- | --- | --- | --- |
| Model-native | token probabilities or a provider confidence field | sometimes none | availability and meaning vary by model and provider |
| Elicited confidence | ask the small model to score its answer | another model call | scores can be coarse, malformed, or poorly calibrated |
| Consistency | compare multiple independently generated answers | multiple samples | agreement depends on the comparison method |
| Critique or verification | ask a model to judge the candidate | another call | the judge can repeat the generator's errors |
| Structural heuristic | parsing, schema validation, or length checks | usually low | detects only the failures represented by the rule |
| External outcome | tests, execution, or human review | task-dependent | may be too slow or unavailable at routing time |

An external outcome can be an excellent offline label even when it cannot be an
online signal. Keep those roles separate: using the answer key to choose the
route measures an oracle policy, not a deployable confidence policy.

## Specify polarity first

For every score, state what a larger value means:

- higher means **retain**;
- higher means **escalate**; or
- the score is categorical and has an explicit mapping.

Then define metrics using the same positive class. A critic that predicts
"retain" has a different operational false-positive error from a detector that
predicts "escalate." Ambiguous polarity can make a good-looking metric describe
the opposite behavior from the policy.

## Preserve the score's support

A nominally continuous score may occupy only a few distinct values. A
three-level score gives a threshold only two meaningful cut points, regardless
of how it is plotted. Inspect:

- the number and frequency of distinct values;
- missing and malformed rates;
- score distributions by outcome;
- stability across task types and time.

Do not silently drop missing values. Dropping them changes the population the
policy sees and can make offline results look better than live behavior.

## Check the signal against memorization

A signal that predicts the small model's success may be reading the model's
competence, or it may be reading the fact that the model has seen the task
before. Those look identical in a pooled metric and behave completely
differently in production, where requests are new by construction.

Split the evaluation on whatever separates "the small model could have
memorized this" from "it could not," and report the discrimination metric on
each side:

- for a public benchmark, the task's release date against the model's training
  cutoff;
- for internal data, records created after the last fine-tune or index refresh;
- for anything else, whatever boundary a plausible leak would have to cross.

A signal whose usefulness survives on the unseen side is measuring something
you can deploy. One that collapses was a memorization artifact.

Two cautions. Vendor-reported cutoffs are approximate, so treat the boundary as
best-effort and report a continuous view — metric against release date — beside
the binary split. And splitting halves your sample on each side: a contrast that
merely fails to reach significance is unresolved, not evidence that exposure
does not matter. The [case
study](../case-studies/escalation-signals-study.md#did-the-signals-survive-contamination-control)
ran this check at 60 problems per cohort and could not resolve it either way.

## Count the signal's marginal cost

Compare signals from the same starting point. A consistency score computed from
three generations has no *additional* call after those generations exist, but it
still presupposes that the system paid for three attempts. An elicited score may
use one extra call per candidate. Include those calls in cost and latency.

## A practical signal contract

Document at least:

```text
name: small-tier confidence
available_when: the small tier returns a candidate
range: finite number in [0, 1]
polarity: higher means retain
aggregation: one score per request
missing_policy: escalate and record "missing-signal"
malformed_policy: escalate and record "malformed-signal"
```

This contract makes the policy testable and keeps provider-specific parsing out
of the routing decision.

## Tiny strict contracts

Keep parsing rules narrower than natural language:

| Parse contract | Valid examples | Malformed examples |
| --- | --- | --- |
| Finite score in `[0, 1]` | `0`, `0.75`, `1` | `NaN`, `-0.1`, `1.2`, `confidence: 0.75` |
| Binary verdict | exactly `PASS` or `FAIL` | `pass`, `PASS because...`, empty text |

For a toy agreement signal that removes spaces, `return a+b` agrees with
`return a + b`. It disagrees with this longer implementation even though the
two programs return the same value:

```python
total = a + b
return total
```

Both comparisons are valid inputs. Exact-string agreement is syntactic, not
semantic equivalence: real programs or open-ended answers can express the same
behavior with different text.

The evaluator implements the valid/missing/malformed score states needed for
its routing lesson. This playbook intentionally omits additional executable
critic and agreement parsers: they would duplicate the same strict-contract
lesson without adding a new cascade concept.

Previous: [Cascade basics](cascade-basics.md)

Next: [Evaluating a cascade](evaluation.md)
