# Contributing to Zscripts

Thanks for investing time in improving Zscripts! This guide explains how to get started, propose changes, and follow the project's engineering standards.

## Ground Rules

- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Use [Conventional Commits](https://www.conventionalcommits.org/) for every commit message.
- Open an issue before large or breaking work; share an execution plan for complex refactors.
- Keep pull requests focused and include tests/docs for any user-visible change.
- Run `python scripts/quality_gate.py quality` (or `make quality`) before
  opening a pull request. This is the complete hosted-CI gate; `make check` is
  the faster contributor gate.
- Annotate TODOs with priority and effort using `TODO(P1, est:4h): context` so
  automation can triage outstanding work.

## Development Environment

1. **Clone & Bootstrap**

   ```bash
   git clone https://github.com/Nobodyworld/dev-logger-zscripts.git
   cd dev-logger-zscripts
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
   python scripts/bootstrap.py
   ```

   The bootstrap script installs the editable package with the development and
   helper extras declared in `requirements.txt`, including the build and
   pre-commit tooling needed by the repository. It then registers the normal and
   commit-message hooks.

2. **One-Command Check**

   ```bash
   make check
   ```

   All commands delegate to `scripts/quality_gate.py` and work directly on
   Windows without GNU Make. The canonical profiles are:

   - `check`: `format-check`, `lint`, `type`, `bandit`, `tests`
   - `quality`: `format-check`, `lint`, `type`, `bandit`, `audit`, `binary`, `tests`, `coverage`, `docs`, `editable-smoke`, `wheel`, `zipapp`, `diagnostics`
   - `release`: `format-check`, `lint`, `type`, `bandit`, `audit`, `binary`, `tests`, `coverage`, `docs`, `editable-smoke`, `wheel`, `zipapp`, `diagnostics`, `redaction`, `gitleaks-worktree`, `gitleaks-history`, `clean`

   `check` is the fast contributor gate. `quality` is the complete hosted-CI
   gate and enforces at least 85% coverage. `release` is the complete local
   release gate; it fails if Gitleaks is unavailable and requires a clean
   worktree. Machine-readable results are written under `reports/`.

3. **Ops Health Probe**

   ```bash
   python scripts/ops_status.py --url http://127.0.0.1:9464
   ```

   Use this helper after enabling telemetry (`--enable-telemetry`) to verify the
   embedded health server responds with `status="ok"`. The script emits a JSON
   payload and non-zero exit codes when degraded, making it suitable for
   post-deploy smoke checks.

4. **Module Scaffolding**

   ```bash
   python scripts/scaffold_module.py --help
   ```

   Use the `extension` subcommand to generate telemetry-aware plugins and the
   `health` subcommand to scaffold reusable registry providers. Both templates
   bind instrumentation, logging, and TODO placeholders so follow-up work is
   traceable.

5. **Pre-commit Hooks**

   - `pre-commit run --all-files` runs Ruff (format + lint), mypy, Bandit, and
     detect-secrets using `.secrets.baseline`.
   - The local commit-message hook runs the standard-library-only
     `scripts/validate_commit_message.py` validator. It does not download
     software or access the network.

6. **Software Bill of Materials (SBOM)**

   - `make sbom` writes local CycloneDX artifacts under `artifacts/sbom/` when
     the `cyclonedx-bom` CLI is installed.
   - SBOM generation is an explicit release-maintenance step; the current hosted
     CI workflow does not publish SBOM artifacts.

7. **Secrets Baseline Maintenance**

   - Update `.secrets.baseline` when adding fixtures that intentionally include
     secret-like strings: `detect-secrets scan > .secrets.baseline`.
   - Review the diff to avoid allow-listing real credentials. The final public
     release gate also runs tracked-file and full-history Gitleaks scans using
     `.gitleaks.toml`.

## Testing

- Write deterministic tests using pytest; prefer property-based tests for parser/config logic.
- When adding fixtures, place reusable assets under `tests/data/` and reference them via helper functions.
- Run `pytest` before opening a PR. For integration-heavy work, add coverage assertions or performance benchmarks when feasible.
- Packaging changes must preserve the hosted editable-install and isolated wheel-install smoke tests.

## Documentation Standards

- Update README.md, relevant docs, and changelog entries for new features.
- Extensions must follow [AGENTS.md](zscripts/extensions/AGENTS.md) and be
  documented in [docs/guides/EXTENSION_GUIDE.md](docs/guides/EXTENSION_GUIDE.md).
- Record dependency rationale updates in `docs/DEPENDENCIES.md` whenever packages change.
- Include inline docstrings and type hints for new modules.
- Capture architectural decisions as ADRs under `docs/adr/`.
- Treat documents under `docs/plans/` as historical planning records unless they
  explicitly identify themselves as current and authoritative.

## Pull Request Checklist

- [ ] Conventional commit history present (squash if necessary).
- [ ] `make check` succeeded locally.
- [ ] Coverage-enforced quality gate succeeded when runtime code changed.
- [ ] Editable and wheel installation smoke tests pass for packaging changes.
- [ ] Tests cover new behaviour or guard against regressions.
- [ ] Docs updated (README, CHANGELOG, STATUS, ADR as needed).
- [ ] Added or updated configuration/schema files when introducing new env vars.
- [ ] Added observability metrics/logs if behaviour changes.

## Release Workflow

- Releases remain manual until an automated release workflow is intentionally
  enabled.
- Add release notes to CHANGELOG.md with context and migration steps.
- Do not tag or publish a release until hosted CI passes and the final
  clean-worktree release gate has been recorded against the exact `main` SHA.

We appreciate your contributions—thank you for helping build a reliable developer experience!
