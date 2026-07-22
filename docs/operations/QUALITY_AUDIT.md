# Quality Audit

## Status Classification

`PUBLIC BETA — ACTIVE DEVELOPMENT`

The repository is public. PR #48 was squash-merged as
`b90a0eefe481c8920f9c413731df3289df75749a`, and PR #53 was squash-merged as
`399792b687549ea97e9319ad9728c7494a0c7ede`. The latter is the exact final SHA
validated locally; neither public visibility nor this audit denotes a stable
release.

## Final Local Audit

| Gate | Result at `399792b687549ea97e9319ad9728c7494a0c7ede` |
|---|---|
| Platform | Windows 11 10.0.26200; Python 3.14.0 |
| Tests | 176 passed; 13 known deprecation warnings |
| Coverage | 92%; required threshold 85% |
| Ruff | Format and lint passed |
| Mypy | Supported surface passed |
| Security | Bandit, dependency audit, and binary scan passed |
| Pre-commit | All files passed |
| Documentation | Link validation passed |
| Packaging | Editable install, isolated wheel, and zipapp smokes passed |
| Runtime evidence | Diagnostics and redaction validation passed |
| Secret scanning | Gitleaks worktree and 109-commit history passed |

Only non-identifying platform evidence is retained; local executable and
workspace paths are not public audit data.

## Hosted Audit

Run `29454174475`, job `88758852806`, failed in the combined security step.
Bandit completed with three existing reviewed `nosec` warnings. `pip-audit`
then returned nonzero because `setuptools 79.0.1` was affected by
`PYSEC-2026-3447`, fixed in 83.0.0. The shell therefore did not reach the binary
scan, tests, coverage, docs, wheel, zipapp, or diagnostics.

The hardening PR makes `setuptools>=83.0.0` part of the development contract,
splits the security commands into named steps, and retains the single required
job/check context `quality`. Public run `29879401419`, job `88796699682`,
completed the full job successfully on commit
`4b59291ac5bdcef281db2ff112e0aff2307824fc`.

## Historical Notes

Earlier PR #47 and PR #48 audit sections captured valid evidence at those points
in time. Their language about awaiting review, merge, publication, or a
visibility change is superseded: PRs #48 and #53 are merged and the repository
is public. Historical limitations and reviewed Bandit suppressions remain
recorded in Git history rather than being presented as current blockers.

Contributor-tooling consolidation remains tracked in issue #61. Legacy helper
disposition remains separately tracked in issue #62 and is outside this audit's
implementation scope.
