# Evaluating a cascade

[Home](../../README.md) / Concepts / Evaluating a cascade

A cascade is useful only if its end-to-end trade-off is better for a specific
workload. Evaluate the complete path rather than a signal metric in isolation.

## Separate labels from decisions

An **offline label** says whether an answer met the evaluation criterion. An
**online signal** is available before the routing decision. Tests, human review,
or a reference answer may create labels; they must not influence a policy that
is presented as deployable unless the production system can run them at that
point.

A simple evaluation flow is:

1. collect small-tier candidates and online signals;
2. obtain outcome labels independently;
3. choose a threshold on calibration data;
4. evaluate the frozen policy on held-out data;
5. report quality, escalation rate, cost, latency, and failures together.

If data is scarce, resampling or cross-validation can quantify uncertainty, but
the split and threshold procedure still need to match the intended claim.

## Resample the independent unit

Repeated generations from one request share the same prompt, task, and often the
same difficulty. They are clustered observations, not independent new
requests. Treating three samples from each of 100 problems as 300 independent
problems makes uncertainty look smaller than the evidence supports.

When estimating intervals or constructing train/test splits, resample or split
at the independent request or problem level. Keep every repeated generation
from one unit together. The appropriate independent unit depends on the claim:
it might be a user, conversation, repository, or problem rather than an
individual model call.

[`examples/clustered_bootstrap.py`](../../examples/clustered_bootstrap.py) does
this, and shows what skipping it costs:

```bash
python3 -m examples.clustered_bootstrap
```

```text
100 problems x 3 samples, samples agree within a problem
resampling                 estimate         95% interval   width
by problem (correct)          0.250       [0.160, 0.330]   0.170
by sample (overconfident)     0.250       [0.200, 0.300]   0.100

resampling by sample understates the interval 1.70x; with k=3 the ceiling is sqrt(3) = 1.73
```

Both rows describe the same data and report the same estimate. The narrower one
is simply wrong about how much evidence it has. With `k` samples per unit and
strong within-unit agreement, the overstatement approaches `sqrt(k)` — so the
error grows with exactly the sampling you added to be more thorough.

Group your observations by the independent unit and pass them to
`bootstrap_ci`; the statistic itself never sees the grouping, only the
resampling does. `naive_bootstrap_ci` exists to make the mistake visible, not
to be used.

## Measure the operating point

Ranking metrics such as AUROC describe whether a score orders examples, not
whether one threshold is useful. At the chosen operating point, report:

- the fraction of requests escalated;
- successful small answers retained;
- failed small answers retained;
- quality after large-tier fallback;
- signal, small-tier, and large-tier cost;
- median and tail latency;
- missing, malformed, timeout, and refusal counts.

Use uncertainty intervals when the sample is intended to support a comparative
claim. An interval that includes no difference does not prove equivalence.

## Account for the whole system

Separate **variable cost** from **fixed cost**. A local endpoint may have almost
no marginal cost per request while still incurring hourly compute cost. A
multi-sample signal may reuse already generated candidates while increasing the
baseline generation cost. Report both views instead of assigning shared cost
arbitrarily.

Also distinguish authorization or budget caps from actual spend. Operational
reserves, retries, and unknown-billing incidents should remain visible rather
than being folded into a clean average.

The offline evaluator keeps three exact `Decimal` buckets:

- **signal cost** pays for confidence, critique, or other routing evidence;
- **variable cost** pays for selected tier usage;
- **fixed cost** pays for infrastructure that remains allocated regardless of
  per-request usage.

Missing or malformed signals still incur signal cost because the system already
attempted to obtain them. A zero variable price does not erase fixed
infrastructure cost. If reasoning usage is unknown, the example marks it
unknown and leaves it out of the known-cost total rather than inventing an
estimate.

Run the deterministic comparison:

```bash
python3 -m examples.evaluate_cascade
```

The synthetic cases make policy accounting inspectable. Small-only never pays
for the large tier, big-only never pays for the small tier, and the threshold
policy provisions both tiers, pays for its small attempt and signal, and retains
a valid score exactly at the threshold. The compact Pareto helper retains exact
ties and removes a policy only when another has no lower quality and no higher
cost, with at least one strict improvement.

A **retained failure** is a wrong small-tier answer that the policy kept. A
**recovered failure** is a wrong small-tier answer replaced by a correct
large-tier answer. Big-only has no retained small answer; any final error remains
visible in overall quality. Its escalation rate is zero because it begins with
the large tier instead of escalating from a small attempt.

## Test for drift

Thresholds can change behavior when prompts, task mix, models, providers, or
prices change. Record the versions and inputs needed to interpret each
evaluation, then monitor:

- signal distributions;
- escalation rate;
- retained-failure rate;
- cost and latency;
- missing or malformed signals.

Recalibrate from new labeled data rather than assuming the original threshold
transfers.

## Read results narrowly

Evaluation supports only the population, tiers, prompts, signal, and procedure
that were measured. Treat model snapshots and provider behavior as part of the
experimental context. See [Limitations](../limitations.md) before adapting the
example to a live system.

Previous: [Escalation signals](escalation-signals.md)

Next: [Latency](latency.md)
