# Provenance

[Home](../README.md) / Provenance

I wrote this playbook. Its [case
study](case-studies/escalation-signals-study.md) reports aggregate results from
a research project I ran privately: the project's repository, data, and
artifacts are not published here and are not needed to use the playbook.

This page records what the case study publishes, what it withholds, and the
separate reasons for each. Those reasons matter, because they are not all the
same kind of reason.

## What the case study publishes

- **The design.** The research question, the problem-selection rule, the
  exposure-cohort split, the registered gate thresholds, the sampling and
  decoding parameters, the serving setup, and the elicitation prompts with their
  parse contracts. These are my own decisions and specifications.
- **Aggregate results.** Point estimates, confidence intervals, confusion
  matrices, cost totals, and per-problem averages, transcribed from my own
  records. No row-level records support them here.
- **An original figure.**
  `docs/case-studies/figures/corrected-context-contrasts.svg` is drawn from the
  transcribed aggregate contrasts. Its SHA-256 is
  `b89a4f539a44601cf10778a3392ed170ef7df117a57e9b1a624cc48b9f898166`.
- **The corrections and incidents.** The withdrawn failure-context
  interpretation, the prompt-format confound behind it, and the endpoint
  cost-accounting failure.

Publishing aggregates without the underlying data raises the standard the
methodology description has to meet, because the design is what a reader can
actually assess. That is why the design section above is detailed rather than
summarized.

## What is not published, and why

### Third-party material I cannot relicense

Benchmark problem statements are not reproduced here, and neither is the frozen
list of admitted problems. The benchmark aggregates tasks from
competitive-programming sites, so the problem text belongs to those platforms
rather than to me or to the benchmark. Separately, that benchmark's design
depends on date-windowed release information to reason about training
contamination; republishing a frozen subset alongside pass/fail labels works
against that purpose.

### Provider outputs

Raw model completions and provider request and response traces are not
published. Output rights generally rest with the API customer, so this is not
primarily an ownership question. I chose not to publish a corpus because current
provider agreements restrict some competitive uses of outputs and those terms
can change; see the [OpenAI Services
Agreement](https://openai.com/policies/services-agreement/) and [Anthropic
Commercial Terms](https://www.anthropic.com/legal/commercial-terms) (accessed
September 1, 2026). Aggregate metrics carry the finding without requiring the
raw corpus.

### My own material, withheld because it is not useful here

Result banks, ledgers, manifests, per-problem records, experiment runners,
provider adapters, pricing locks, and budget and gate machinery are mine to
publish and are simply out of scope. The playbook teaches a design pattern and
does not need them. Nothing here is a licensing constraint, and nothing here
claims to reproduce the study.

## Licensing

The Apache-2.0 license covers this playbook's own prose, examples, and tests. It
does not extend to the benchmark, to provider outputs, or to any other
third-party material the case study discusses; each of those keeps its own
status. This page records how I drew the boundary. It is not legal advice and
not a guarantee about third-party rights.

## Claim-handling policy

The playbook keeps reusable guidance separate from the case study. Statements
from the case study are conditional on its documented problem subset, model
revisions, prompts, and analysis rules. Superseded work is labeled superseded;
canceled or unavailable work is never described as a negative result.

Contributions that add an empirical claim should cite an accessible source,
state the evaluated population and model versions, and link the relevant
limitations. See [Contributing](../CONTRIBUTING.md).

Previous: [Limitations](limitations.md)

Next: [Home](../README.md)
