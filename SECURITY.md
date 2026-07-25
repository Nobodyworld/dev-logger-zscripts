# Security Policy

## Supported Versions

Zscripts is published as **PUBLIC BETA — ACTIVE DEVELOPMENT**. Security fixes are
provided on a best-effort basis for the current `main` branch. No older release
line is currently guaranteed support.

| Version | Supported |
| --- | --- |
| `main` | Best-effort security fixes |
| Tagged pre-1.0 releases | Not independently supported unless stated in release notes |

## Reporting a Vulnerability

Use GitHub private vulnerability reporting through the repository **Security**
tab. Include a clear description, reproduction steps, affected versions or
commits, and the likely impact.

- Do **not** disclose vulnerability details in a public issue, discussion, or pull
  request.
- If private vulnerability reporting is temporarily unavailable, do not publish
  sensitive details. Use a verified private contact method listed by the
  repository owner on GitHub, or wait until private reporting is available.
- This project does not currently publish a dedicated security mailbox, PGP key,
  or guaranteed response-time service level.

## Handling Process

Maintainers will, as capacity permits:

1. Triage and attempt to reproduce the report.
2. Assess severity and affected surfaces.
3. Develop and test a fix in a non-public workstream when appropriate.
4. Coordinate disclosure with the reporter.
5. Publish a GitHub Security Advisory and update project documentation when a
   disclosure is warranted.

Response and remediation timing depends on severity, reproducibility, maintainer
availability, and the scope of the required fix.

## Security Tooling

The hosted quality gate includes:

- Ruff formatting and linting;
- the supported mypy target;
- Bandit;
- `pip-audit`;
- binary-file scanning;
- pytest with an enforced coverage threshold;
- editable-install, wheel, zipapp, and diagnostics smoke tests.
- hostile repository fixtures, read-only/cancellation/rollback contracts,
  localhost API validation, frontend tests, and packaged-workspace smoke tests.

The local `release` profile additionally validates report redaction, requires
Gitleaks scans of the tracked worktree and repository history, and verifies a
clean worktree. GitHub secret scanning, push protection,
Dependabot alerts and security updates, CodeQL where eligible, and private
vulnerability reporting should be enabled or verified immediately after the
repository becomes public.

## Repository-review threat model

The experimental workspace treats every analyzed repository as hostile input.
It uses bounded byte reads and Python AST parsing only, never imports target
modules, never runs framework setup, and never derives a shell command from
repository contents. Read-only Git metadata queries use a fixed no-shell
allowlist with hooks and optional locks disabled. Symlinks are excluded.

The only Bandit exemptions added for this slice cover that fixed Git invocation
and SQL query fragments assembled from fixed, allowlisted column/direction
tokens; all user values are bound parameters. Tests exercise inert fixtures that
would write files, run commands, open sockets, perform HTTP requests, read
environment secrets, invoke framework setup, and raise at import time if the
analyzer ever executed them.

The application stores metadata outside the repository and binds the workspace
only to `127.0.0.1` with same-origin routes and restrictive browser headers.
Source excerpts are explicit, bounded, hash-verified, never persisted, and may
still contain sensitive source text in the local browser. Static analysis does
not establish that a repository is safe. See
[the repository-review privacy contract](docs/repository-review.md#read-only-and-privacy-contract).

## Responsible Disclosure

Coordinated disclosure is appreciated. Reporters may request attribution or
anonymity. Please allow the maintainer a reasonable opportunity to investigate
and remediate before public disclosure.

## Pre-release Security Checklist

- [ ] Run the complete hosted and local release gates.
- [ ] Confirm coverage meets the configured threshold of 85% or higher.
- [ ] Review dependency advisories with `pip-audit`.
- [ ] Run tracked-worktree and full-history Gitleaks scans.
- [ ] Verify generated reports do not expose fixture or provider-shaped secrets.
- [ ] Confirm configuration changes are documented and secrets are loaded from
      environment variables or secure stores.
- [ ] Update `CHANGELOG.md` and release notes for security-impacting changes.
