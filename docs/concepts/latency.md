# Latency

[Home](../../README.md) / Concepts / Latency

Cost analysis treats the small attempt and the routing signal as overhead you
might recover. Latency does not work that way, because the escalated path runs
the tiers **in sequence**. A cascade can lower average latency while making the
slow requests slower, and the slow requests are usually the ones people notice.

## The escalated path is strictly worse

Write `L_small`, `L_signal`, and `L_large` for the three stages. Post-attempt
escalation gives two paths:

```text
retained:   L_small + L_signal
escalated:  L_small + L_signal + L_large
```

Compare that with calling the large tier directly, which always costs
`L_large`. The retained path is faster. The escalated path is **always slower
than big-only**, by exactly the overhead `L_small + L_signal`, and no routing
accuracy changes that. Expected latency is:

```text
E[latency] = L_small + L_signal + rate * L_large
```

This is the same shape as the cost equation in
[`examples/cascade_economics.py`](../../examples/cascade_economics.py), with
one important difference: cost is a budget you can average over a month, and
latency is experienced one request at a time.

## Averages hide the damage

Suppose the small tier plus signal takes 200 ms, the large tier takes 2,000 ms,
and the policy escalates 20% of requests.

| | Big-only | Cascade |
| --- | ---: | ---: |
| Mean | 2,000 ms | 640 ms |
| Requests at ~200 ms | 0% | 80% |
| Requests at ~2,200 ms | 0% | 20% |
| p95 | 2,000 ms | 2,200 ms |

Mean latency drops by more than a factor of three, and the p95 gets *worse*.
If your service level objective is written on a tail percentile — and most are
— a cascade that looks like a large win on the average can fail the objective
it is measured against.

The crossover is straightforward: whenever the escalation rate exceeds
`1 - p`, the p-th percentile of the cascade sits on the escalated path and is
therefore worse than big-only. At a 20% escalation rate, every percentile above
the 80th is worse.

## What follows from that

- **Report the percentile your objective uses**, not the mean. A mean that
  improves while the tail regresses is the normal case, not an edge case.
- **Budget the signal in milliseconds too.** An elicited score is another
  round trip on the critical path of *every* request, including the ones that
  go on to escalate anyway.
- **Consider where the overhead lands.** Escalation puts the extra latency on
  the requests the small tier already handled badly, which correlates with
  harder requests and often with more demanding users.
- **Streaming complicates the retained path.** If the small tier streams, a
  routing decision that needs the complete answer removes the time-to-first-
  token benefit that made the small tier feel fast.

## When the sequence can be broken

Two escape hatches, both with a price:

**Pre-generation routing** decides before any generation, so there is no
discarded attempt and no serial overhead. It gives up the information in the
candidate itself, which is the thing post-attempt escalation exists to use.

**Speculative execution** starts both tiers at once and cancels the large-tier
call when the signal says retain. That recovers the tail — the escalated path
becomes roughly `L_large` again — by paying for large-tier calls you often
throw away. It converts a latency problem into a cost problem, and the
break-even analysis then has to assume you pay for the large tier on close to
every request, which usually puts it beyond the ceiling in
[Cascade economics](../../examples/cascade_economics.py).

Neither is free. Both are better than discovering the tail regression in
production.

Previous: [Evaluating a cascade](evaluation.md)

Next: [Should you cascade?](../decision-checklist.md)
