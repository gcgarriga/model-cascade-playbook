# Cascade basics

[Home](../../README.md) / Concepts / Cascade basics

A model cascade uses more than one model tier and a policy that decides which
tier should answer. The usual goal is to reserve a capable, expensive, or slow
tier for requests where it adds enough value to justify its cost.

This playbook emphasizes **post-attempt escalation**:

```text
request -> small tier -> candidate -> signal -> policy
                                             | retain
                                             v
                                          response
                                             ^
                                             | escalate
                                          large tier
```

That differs from **pre-generation routing**, where a policy chooses a tier
before any model produces an answer. Pre-generation routing can be cheaper
because it avoids a discarded small-tier call. Post-attempt escalation can use
information from the candidate itself, but the signal and discarded attempt
also consume time or compute.

## The five moving parts

1. **Small tier** produces the first candidate. "Small" is relative: it can mean
   fewer parameters, lower price, lower latency, local execution, or a restricted
   reasoning budget.
2. **Signal** summarizes evidence about whether that candidate should be
   retained. A score is useful only when its direction and failure behavior are
   explicit.
3. **Policy** maps the signal to a decision. A threshold is the simplest policy,
   but the threshold must be calibrated for the task and operating costs.
4. **Large tier** produces a replacement after escalation. It should not be
   called on retained requests.
5. **Measurement** records quality, routing, cost, latency, and failures. Without
   measurement, a cascade is only an intuition about savings.

## A minimal decision

Suppose a small tier returns a confidence score in the closed interval from 0 to
1. A threshold policy might retain scores at or above 0.7 and escalate lower
scores:

```text
score >= 0.7 -> retain the small answer
score <  0.7 -> call the large tier
```

This notation does not make 0.7 a generally good threshold. The right threshold
depends on the task, the score's calibration, the cost of a bad retained answer,
and the marginal cost and latency of escalation.

Unknown inputs need a deliberate policy. The teaching example in
[`examples/minimal_cascade.py`](../../examples/minimal_cascade.py) escalates when
the score is missing, non-finite, or outside the expected range and records why.
That is a conservative default, not a universal requirement.

## Start with one explicit loop

For a first implementation:

- use one small tier and one large tier;
- define one signal with documented polarity and range;
- make the policy a pure, inspectable function;
- return the selected tier and decision reason with the answer;
- evaluate against task-relevant outcomes before production use.

Add more tiers, learned policies, or parallel calls only when a measured
constraint requires them.

Previous: [Home](../../README.md)

Next: [Escalation signals](escalation-signals.md)
