# Should you cascade?

[Home](../README.md) / Decision checklist

Work through this before building a router. Each question has a cheap answer
now and an expensive answer after deployment. The questions are ordered so the
ones that can stop the project come first.

## 1. Is there a price gap worth crossing?

Compute the ceiling before anything else:

```bash
python3 -m examples.cascade_economics \
  --small-cost 0.001 --large-cost 0.010 --signal-cost 0.001
```

This reports `rate* = 1 - (small + signal) / large`, the escalation rate above
which the cascade costs more than simply calling the large tier — regardless of
how good the routing is.

- **`rate*` at or near zero** → stop. The small attempt plus its signal already
  cost about what the large tier costs. No signal can rescue this.
- **`rate*` below your expected escalation rate** → stop, or make the signal
  cheaper. You cannot route your way past the arithmetic.
- **`rate*` comfortably above it** → continue.

## 2. Can the small tier actually do the work?

If the small tier's quality on your traffic is far below the large tier's, the
policy will escalate nearly everything, and you will pay the overhead on every
request to buy the large-tier answer anyway. Measure the small tier alone on
representative traffic first. A cascade cannot exceed what the small tier can
already do on the requests it keeps.

## 3. Will the answers you keep be good enough?

Cascade quality is `(1 - rate) * retained + rate * large`. Requiring that to
match big-only reduces to a condition the escalation rate drops out of
entirely:

> The small answers the policy **retains** must be at least as good as the
> large-tier answers it declined to buy.

So the question is never "does it escalate enough". It is whether the signal
can identify the requests where the small tier is genuinely sufficient.

## 4. Do you have a signal, or just a number?

For each candidate signal, fill in
[`examples/signal_contract.toml`](../examples/signal_contract.toml). If you
cannot complete it, you do not yet have a signal. In particular:

- **Polarity** stated before any metric is computed.
- **Missing and malformed policy** — never silently dropped, because dropping
  changes the population the policy sees.
- **Distinct values actually observed.** A score that looks continuous but
  takes three values gives a threshold two usable cut points.
- **Marginal cost**, counted from the same starting point as its alternatives.

## 5. Is the signal measuring competence or memory?

Split your evaluation on whatever separates "the model could have seen this"
from "it could not," and report the metric on both sides. A signal that
collapses on unseen data was a memorization artifact. See [Check the signal
against memorization](concepts/escalation-signals.md#check-the-signal-against-memorization).

## 6. Which latency number are you judged on?

A cascade usually improves the mean and worsens the tail, because escalated
requests pay both tiers in sequence. If your objective is a tail percentile,
check the crossover: above an escalation rate of `1 - p`, the p-th percentile
is worse than big-only. See [Latency](concepts/latency.md).

## 7. Can you tell whether it is still working?

Before deployment, decide what you will watch and what will make you turn it
off: signal distribution, escalation rate, retained-failure rate, cost per
request, tail latency, and missing or malformed rates. A cascade drifts when
prompts, models, providers, or prices change, and the failure mode is silent —
a parser change can move every request to one tier without any error.

## 8. Have you compared against the boring baselines?

Run the comparison on your own numbers:

```bash
python3 -m examples.evaluate_cascade --cases your_workload.csv --sweep
```

The cascade should have to beat small-only and big-only on the Pareto frontier
before it earns its complexity. Compare it against random escalation at the
same rate, too: if a coin flip at your escalation rate does as well, your
signal is not doing the work — the escalation rate is.

## If you stopped

Stopping here is a result, not a failure. The most common honest outcome is
that a cascade is not worth it for a given workload, and finding that out from
arithmetic is much cheaper than finding it out from a router in production.

Previous: [Latency](concepts/latency.md)

Next: [Case study](case-studies/escalation-signals-study.md)
