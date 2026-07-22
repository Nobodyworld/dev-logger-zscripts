# Public Release Final Verdict

## Current Status

- Classification: `PUBLIC BETA — ACTIVE DEVELOPMENT`
- Repository visibility: public
- Final locally validated `main` SHA: `399792b687549ea97e9319ad9728c7494a0c7ede`
- PR #48 was squash-merged as `b90a0eefe481c8920f9c413731df3289df75749a`.
- PR #53 was squash-merged as `399792b687549ea97e9319ad9728c7494a0c7ede`.

This is a public beta, not a stable release. No tag or GitHub Release is implied
by repository visibility or by the validation evidence below.

## Final Local Validation Record (2026-07-16)

The exact SHA above passed the clean Windows release gate with Python 3.14.0.
The non-identifying retained evidence is:

- YAML/TOML parsing and dependency checks passed;
- Ruff formatting and linting passed;
- the supported mypy surface passed;
- the binary scan passed;
- 176 tests passed with 13 known deprecation warnings;
- coverage was 92%, above the 85% threshold;
- documentation-link validation and pre-commit passed;
- editable-install, isolated-wheel, and zipapp smokes passed;
- diagnostics JSON and report-redaction validation passed; and
- Gitleaks worktree and 109-commit history scans found no leaks.

Machine-specific executable and workspace paths are intentionally not retained
in this public record.

## Hosted Public CI

Public GitHub Actions run `29454174475` reached the `quality` job on Ubuntu and
failed in the combined security step. Bandit completed, then `pip-audit` found
`setuptools 79.0.1` affected by `PYSEC-2026-3447` (fixed in 83.0.0). Because the
shell stopped at that failure, the binary scan and later test, package, docs, and
diagnostics steps did not run. Issue #60 tracks that root cause.

The hardening PR constrains the development toolchain to the fixed setuptools
release and keeps the single required status-check context named `quality`.
Public run `29879401419`, job `88796699682`, completed that full job
successfully on commit `4b59291ac5bdcef281db2ff112e0aff2307824fc`.

## Historical Context

PR #47 established the earlier showcase baseline. PR #48 then aligned the
public-beta narrative, packaging, validation, and security-reporting policy; PR
#53 normalized tracked files for pre-commit. Earlier documents describing PR
#48 as awaiting review, merge, or publication are historical planning evidence,
not current repository state.

Sensitive vulnerability reports remain governed by `SECURITY.md`. Public
issues, discussions, and pull requests must not contain sensitive disclosure
details.

## Final Classification

`PUBLIC BETA — ACTIVE DEVELOPMENT`

The project remains actively developed. Outputs should be reviewed before
production use or publication, and automated redaction remains defense in depth
rather than a guarantee.
