# Contributing to Zscripts

Thanks for investing time in improving Zscripts! This guide explains how to get started, propose changes, and follow the project's engineering standards.

## Ground Rules
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Use [Conventional Commits](https://www.conventionalcommits.org/) for every commit message.
- Open an issue before large or breaking work; share an execution plan for complex refactors.
- Keep pull requests focused and include tests/docs for any user-visible change.
- Run `python scripts/dev_start.py` (or `make quality`) before opening a pull
  request. The quality gate enforces lint/type/security/tests and ≥85%
  coverage.
- Annotate TODOs with priority and effort using `TODO(P1, est:4h): context` so
  automation can triage outstanding work.

## Development Environment
1. **Clone & Bootstrap**
   ```bash
   git clone https://github.com/zscripts/zscripts.git
   cd zscripts
   python -m venv .venv
   source .venv/bin/activate
   python scripts/bootstrap.py
   ```
   The bootstrap script installs runtime/dev dependencies and registers
   `pre-commit` hooks (including commit message validation).
2. **One-Command Check**
   ```bash
   python scripts/agent_guard.py
   ```
   This runs lint, type checks, Bandit, and pytest. Use `--only`/`--skip` to
   tailor the workflow; `make quality` remains available for coverage-enforced
   pipelines and writes summaries to `artifacts/quality/quality_gate.json`.

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
   - `pre-commit run --all-files` runs Ruff (format + lint), mypy, Bandit, and detect-secrets using `.secrets.baseline`.
   - Commit-msg hooks run `npx commitlint --edit "$1"`; ensure Node.js ≥18 is installed locally.

6. **Software Bill of Materials (SBOM)**
   - Generate CycloneDX manifests with `make sbom`; artifacts are written to `artifacts/sbom/` and uploaded by CI for Python 3.11 runs.
   - Ensure the directory stays in `.gitignore`. If the command fails, verify that `cyclonedx-bom` is installed from `requirements.txt`.

7. **Secrets Baseline Maintenance**
   - Update `.secrets.baseline` when adding fixtures that intentionally include secret-like strings: `detect-secrets scan > .secrets.baseline`.
   - Review the diff to avoid allow-listing real credentials. CI also runs gitleaks with `.gitleaks.toml` for defense in depth.

## Testing
- Write deterministic tests using pytest; prefer property-based tests for parser/config logic.
- When adding fixtures, place reusable assets under `tests/data/` and reference them via helper functions.
- Run `pytest` before opening a PR. For integration-heavy work, add coverage assertions or performance benchmarks when feasible.

## Documentation Standards
- Update README.md, relevant docs, and changelog entries for new features.
- Extensions must follow [AGENTS.md](zscripts/extensions/AGENTS.md) and be
  documented in [docs/guides/EXTENSION_GUIDE.md](docs/guides/EXTENSION_GUIDE.md).
- Record dependency rationale updates in `docs/DEPENDENCIES.md` whenever packages change.
- Include inline docstrings and type hints for new modules.
- Capture architectural decisions as ADRs under `docs/adr/`.

## Pull Request Checklist
- [ ] Conventional commit history present (squash if necessary).
- [ ] `make check` succeeded locally.
- [ ] Tests cover new behaviour or guard against regressions.
- [ ] Docs updated (README, CHANGELOG, STATUS, ADR as needed).
- [ ] Added or updated configuration/schema files when introducing new env vars.
- [ ] Added observability metrics/logs if behaviour changes.

## Release Workflow
- Releases are automated once semantic-release is enabled. Until then, maintainers tag versions manually after verifying CI.
- Add release notes to CHANGELOG.md with context and migration steps.

We appreciate your contributions—thank you for helping build a reliable developer experience!
