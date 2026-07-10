# Public Release Final Verdict

- Repository: `Nobodyworld/dev-logger-zscripts`
- Branch reviewed: PR #48, `chore/public-showcase-readiness-followup`
- Current merged showcase baseline: `7d6e03f4674c22401e8d15a57b02f856941fed55`
- Last clean-worktree product-validation source head: `124c1e4f85204aaec76d4f7feafdbd0912513bd7`
- Evidence updated: 2026-07-10
- Authoritative status: `KEEP PRIVATE - LOCAL PR VALIDATION AND FINAL MAIN VALIDATION REQUIRED`

## Employer-Facing Product Identity

Zscripts converts raw development and CI logs into normalized, redacted,
diagnosable, and reportable output through a reusable Python CLI and adapter
architecture.

Core identity in scope:

- Log normalization
- Redaction
- Diagnostics
- Reporting
- Adapter architecture

Explicitly out of core identity:

- Legacy helper collection under `zscripts/helpers` (optional extras only)

## Current Public-Showcase Improvements

PR #47 was squash-merged into `main` as
`7d6e03f4674c22401e8d15a57b02f856941fed55`.

That merge:

- fixed Windows stdin probing for unsupported `select` handles;
- replaced provider-shaped and hardcoded demo secrets in public examples;
- required sample Docker Compose secrets to come from local environment values;
- corrected CLI examples so global `--adapter` precedes the subcommand;
- fixed report redaction so normalized report fields are redacted before
  Markdown/JSON rendering;
- added regression tests for report redaction and CLI argument order.

PR #48 adds or updates:

- least-privilege GitHub Actions permissions and immutable Action SHA pins;
- disabled checkout credential persistence;
- Dependabot grouping and lower open-PR limits;
- removal of the broad Gitleaks path allowlist;
- explicit setuptools discovery for the runtime `zscripts`, `adapters`, `agents`,
  and `scripts` package trees;
- deterministic full-environment bootstrap and contributor instructions;
- editable-install, isolated-wheel, and zipapp smoke coverage in hosted CI;
- hosted coverage enforcement and documentation-link validation;
- corrected pre-commit Bandit paths and a non-mutating `make check`;
- current release-status documentation and a historical banner on stale planning
  material.

## Latest Clean-Worktree Validation Evidence

The merged PR #47 product baseline was validated locally before merge from clean
worktree head `124c1e4f85204aaec76d4f7feafdbd0912513bd7`.

Reported validation results:

- Formatting: pass (`ruff format --check .`)
- Lint: pass (`ruff check .`)
- Binary scan: pass (`python scripts/no_binaries.py`)
- Test suite: pass (`176 passed, 13 warnings` with pytest temp base outside the repo)
- Documentation links: pass (`python scripts/validate_docs_links.py`)
- Whitespace diff check: pass (`git diff --check`)
- Mypy supported surface: pass
- Coverage: pass (92%, threshold 85%)
- Zipapp build: pass (`artifacts/build/zscripts.pyz`)
- Packaged guardrails smoke: pass
- Packaged adapter-inventory smoke: pass
- Raw-log-to-redacted-report demo: pass with supported CLI argument order
- Generated report redaction scan: pass, no unredacted fixture or common provider-token patterns
- Bandit: pass under Python 3.14.0
- Dependency audit: pass (`python -m pip_audit`)
- Gitleaks tracked-file scan: pass
- Gitleaks full-history scan: pass

This is strong product evidence, but it predates the complete PR #48 branch and
cannot serve as the final visibility-change gate.

## Current GitHub Actions Status

GitHub Actions run #20 passed against PR #48 head
`8b80c74d974658ae6d6480c3c171bba6f7507e9d` under Ubuntu and Python 3.11.

The hosted gate passed:

- full editable installation with `.[dev,helpers]`;
- editable imports and CLI smokes outside the repository root;
- Ruff formatting and lint;
- the supported mypy surface;
- Bandit, dependency audit, and binary-file scanning;
- all 176 tests with the 85% coverage threshold enforced;
- documentation-link validation;
- isolated wheel build, installation, imports, and CLI smokes;
- zipapp build and CLI smokes;
- diagnostics snapshot generation;
- quality-report artifact upload.

This resolves the prior run #8 diagnostics failure. The branch now has hosted
evidence that the source checkout, editable install, built wheel, and zipapp all
execute through their supported entry points.

## CodeQL and Secret Protection Status

The repository is currently private under an account without private-repository
GitHub Code Security / Secret Protection coverage.

Current classifications:

- CodeQL: `DEFERRED UNTIL PUBLIC OR LICENSED`
- GitHub Secret Protection: `DEFERRED UNTIL PUBLIC OR LICENSED`
- Push protection: `DEFERRED UNTIL PUBLIC OR LICENSED`

Do not add an active CodeQL workflow while the repository remains private and
unlicensed. Enable the deferred GitHub security features immediately after the
repository becomes public or qualifying coverage is available.

## Remaining Public-Showcase Blockers

- The complete latest PR #48 head must pass the clean-worktree release gate
  locally.
- The final PR head and local validation results must be recorded before the PR
  is marked ready and merged.
- PR #48 must be reviewed and squash-merged with an expected-head safety check.
- A final clean-worktree validation must be run against the exact merged `main`
  commit after all follow-up changes are included.
- The published security mailbox, PGP fingerprint, and response commitments must
  be confirmed as operational before visibility changes.
- Repository branch protection, required checks, visibility, and deferred
  security-feature settings must be confirmed by the owner because those settings
  are not fully exposed through the connector.

## Final Classification

`KEEP PRIVATE - LOCAL PR VALIDATION AND FINAL MAIN VALIDATION REQUIRED`

## Owner Steps Before Visibility Change

1. Run the full clean-worktree release gate on the latest PR #48 head.
2. Update this evidence with the exact validated PR head and results.
3. Mark PR #48 ready and perform the final review.
4. Squash-merge PR #48 with an expected-head safety check.
5. Run the full clean-worktree release gate again on the exact merged `main` SHA.
6. Confirm no realistic provider-shaped secrets remain in tracked files or history.
7. Confirm the security reporting contact and PGP information are functional.
8. Confirm branch protection and required-check settings for the public state.
9. Change visibility only after every preceding gate remains green.
10. Immediately after publication or licensing, enable the deferred GitHub security features.
