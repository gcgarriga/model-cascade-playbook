# Contributing

Thank you for helping make model cascades easier to understand and evaluate.

## Choose the right section

- Put reusable explanations in `docs/concepts/`.
- Put study-specific material in `docs/case-studies/`.
- Add constraints or non-transferable assumptions to `docs/limitations.md`.
- Record what the case study publishes and withholds in `docs/provenance.md`.
- Keep code under `examples/` small, deterministic, and focused on one teaching
  outcome.

Do not add provider integrations, paid calls, benchmark datasets, raw model
outputs, result banks, provider traces, or preregistration machinery without
prior agreement on scope.

Report a suspected vulnerability or an accidental disclosure privately, through
[GitHub Security Advisories](https://github.com/gcgarriga/model-cascade-playbook/security/advisories/new),
never in a public issue. This GitHub-native path deliberately replaces a
separate security-policy file.

## Claims and evidence

Write guidance as a decision frame, not as a universal performance claim. For
empirical statements:

1. cite an accessible source;
2. state the tasks, model versions, prompts, and evaluation population;
3. distinguish a missing, canceled, or unrun result from a negative result;
4. label post-hoc observations and superseded analyses;
5. link the relevant limitations.

Do not add benchmark payloads, raw model outputs, provider traces, or per-problem
records to the playbook. Update `docs/provenance.md` when a change moves the
boundary it records.

## Example code

Examples should:

- run without credentials or network access;
- use no runtime dependency unless it is essential to the lesson;
- expose routing decisions and failure behavior;
- avoid implying that simulated scores are calibrated;
- include focused tests for retain, escalate, and error paths.

## Local checks

The examples target Python 3.11 or later. Continuous integration runs the full
check suite on Python 3.11 and 3.12.

Use the install and check commands in
[Agent Instructions](AGENTS.md#commands). Tool versions are pinned once in
`requirements-dev.txt`.

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m ruff check . && python3 -m ruff format --check . && python3 -m mypy . && python3 -m pytest -q
```

When changing behavior, first write a test that fails for the intended reason.
Before trusting the new test, make a temporary behavior mutation and confirm the
test detects it, then restore the implementation.

## Repository settings

For discoverability, maintainers should use a small topic set such as
`model-cascades`, `llm-routing`, `cost-aware-inference`, `evaluation`, and
`education`. Topics describe the playbook; they are not evidence claims.

## Pull requests

Keep each pull request focused. Explain:

- the learner problem it solves;
- where the new material sits in the learning path;
- how claims were sourced and bounded;
- which commands verified the change.

Run the repository checks and ask another contributor to review substantial
behavior changes. Contributions are accepted under the
[Apache License 2.0](LICENSE).
