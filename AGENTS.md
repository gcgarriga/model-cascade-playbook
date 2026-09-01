# Agent Instructions

## Commands

| Task    | Command                                                                |
| ------- | ---------------------------------------------------------------------- |
| Install | `python3 -m pip install -r requirements-dev.txt`                        |
| Test    | `python3 -m pytest -q`                                                  |
| Lint    | `python3 -m ruff check . && python3 -m mypy .`                                                |
| Format  | `python3 -m ruff format .`                                                         |
| Check   | `python3 -m ruff check . && python3 -m ruff format --check . && python3 -m mypy . && python3 -m pytest -q` |

## Rules

- Treat this file as the only repository-specific agent instruction source.
- Read relevant code before answering. Ground every claim in inspected files.
- Make surgical, atomic changes. One logical change per commit.
- Run the test command before every commit.
- Use conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- No bare `except:`. No commented-out code. No global mutable state.
- Write or update tests alongside every behaviour change.
- A check that has never failed is unverified: before trusting a green run, break what it guards and confirm it goes red.
- Beware vacuous passes: a rule over "all X" holds when X is empty, and a total over groups holds when one group is zero. Assert per group that the check examined something.
- Write original playbook prose. Keep case-study claims conditional on their documented population, model revisions, and analysis rules.
- Keep reusable concepts, case studies, limitations, and provenance in their designated sections.
- Keep examples deterministic, provider-neutral, and runnable without credentials or network access.
- Ask a reviewer to check requirement compliance and code quality for substantial changes.

## Boundaries

### Always

- Run lint and tests before claiming done.
- Keep changes branch-based and use pull requests for public contributions.
- Label teaching simulations and case-study evidence explicitly.

### Ask first

- Broad refactors or architectural changes.
- Adding, upgrading, or removing dependencies.
- Changing a public interface or API contract.
- Adding provider integrations, network calls, benchmark runners, or empirical result data.

### Never

- Commit secrets, credentials, or tokens.
- Leave the test suite red.
- Rewrite git history unless explicitly requested.
- Publish benchmark payloads, raw model outputs, provider traces, result banks, or per-problem records.
- Present one case study as general evidence that a routing signal or cascade policy works.
- Describe a canceled or unrun result as a negative result.
