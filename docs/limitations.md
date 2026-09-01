# Limitations

[Home](../README.md) / Limitations

This repository teaches a design pattern. It does not establish that a cascade
will improve quality, cost, or latency for a particular workload.

## The runnable examples are simulations

[`examples/minimal_cascade.py`](../examples/minimal_cascade.py) uses deterministic
tiers and a caller-supplied confidence score. It demonstrates control flow and
failure handling only. It does not:

- call or compare real models;
- calibrate the score or recommend the default threshold;
- measure quality, cost, or latency;
- model concurrency, retries, rate limits, streaming, or partial failures;
- handle sensitive prompts or provider data-retention policies.

Do not treat its output as empirical evidence.

[`examples/evaluate_cascade.py`](../examples/evaluate_cascade.py) adds synthetic
correctness labels, token counts, prices, and fixed costs. They exist to make
accounting inspectable, not to approximate any provider, deployment, or expected
economic result. Its two built-in scenarios are chosen to show routing losing
and routing winning; neither is a prediction, and the favorable one is not
evidence that a cascade will pay off for you.

[`examples/cascade_economics.py`](../examples/cascade_economics.py) is
arithmetic on numbers you supply. It does not measure your costs, estimate your
escalation rate, or know whether your retained answers are good enough. A
break-even rate computed from guessed inputs is a guess with a decimal point on
it. Its ceiling is also a necessary condition, not a sufficient one: clearing it
means the cascade is not obviously doomed on cost, not that it is worth
building.

## Real signals can fail silently

A confidence field can change meaning across model or provider versions.
Elicited confidence and critique add calls and may share the generator's blind
spots. Consistency depends on how outputs are compared. Structural rules detect
only the failures they encode.

Record missing and malformed values rather than dropping them. Monitor signal
support and routing rates so that a parser or provider change does not silently
move every request to one tier.

## End-to-end economics are workload-specific

An escalation can add the latency of both tiers. A small endpoint may have fixed
uptime cost. Multi-sample or critique signals may cost more than the savings
they enable. The large tier can still fail after escalation.

Measure the complete path on representative traffic, including:

- retained failures and recovered failures;
- escalation rate;
- signal, small-tier, and large-tier cost;
- median and tail latency;
- timeouts, refusals, retries, and unknown billing;
- fixed infrastructure cost.

## Evaluation can leak answers

Tests, reference outputs, and human judgments are useful labels. They are not
deployable signals unless the production system can access them before routing.
Keep label generation separate from policy inputs and freeze thresholds before
held-out evaluation.

## Models and workloads drift

Results do not transfer automatically across prompts, languages, model
snapshots, providers, quantization, or task distributions. Re-evaluate after
changing any of those inputs and monitor the deployed operating point.

## The case study is narrow

The [escalation-signals case study](case-studies/escalation-signals-study.md)
is an account of my own research project, with explicit scope and known gaps.
It is included for lessons about experimental discipline, not as a benchmark or
universal recommendation.

Its numbers come from 120 tasks drawn from one programming-task benchmark, three
small-model samples per task, one fixed small-model revision, and exact
larger-model snapshots. The 120 were **selected to have headroom**: admitted only
if both larger models could solve them and the small model mostly could not. That
filter makes escalation look more valuable than it would on unfiltered traffic.
The failure-context phase narrows further to the 106 of those tasks where the
small tier had already failed, so its contrasts cannot describe the whole
cascade's cost-quality trade-off. Its exposure-cohort contrasts are unresolved at
60 problems per cohort rather than null. Hosted responses vary from call to call,
and the correction does not serve as a separately conceived repeat.

See [Evaluating a cascade](concepts/evaluation.md) for an evaluation frame and
[Provenance](provenance.md) for the source boundary.

Previous: [Escalation-signals case study](case-studies/escalation-signals-study.md)

Next: [Provenance](provenance.md)
