# Clean-Clone Release Validation

- Repository: `Nobodyworld/dev-logger-zscripts`
- Historical validation date: 2026-07-08
- Historical branch context: PR #47 / merged showcase baseline
- Merged `main` baseline: `7d6e03f4674c22401e8d15a57b02f856941fed55`
- Historical clean-worktree source head: `124c1e4f85204aaec76d4f7feafdbd0912513bd7`
- Historical environment: Windows clean worktree, Python 3.14.0
- Intended public status: `PUBLIC BETA — ACTIVE DEVELOPMENT`
- Current status: `PR #48 LOCAL AND FINAL MAIN VALIDATION REQUIRED`

## PR #48 Hosted Revalidation

GitHub Actions run #23 passed against PR #48 head
`14bcfb545c92fc196911ce4a0b8114f0c16e095b` under Ubuntu and Python 3.11.

The hosted gate completed successfully:

- installation of `.[dev,helpers]`;
- editable-package imports and CLI smokes outside the repository root;
- Ruff formatting and lint;
- the supported mypy surface;
- Bandit, dependency audit, and binary-file scan;
- all 176 tests with the 85% coverage threshold enforced;
- documentation-link validation;
- isolated wheel build, installation, imports, and CLI smokes;
- zipapp build and CLI smokes;
- diagnostics snapshot generation;
- quality-report artifact upload.

This resolves the earlier diagnostics and package-discovery failures. Package
discovery explicitly includes the runtime `zscripts`, `adapters`, `agents`, and
`scripts` package trees.

Later documentation commits remove unverified security-contact claims and add the
public-beta classification and limitations. The complete latest PR #48 head must
receive both hosted and local validation before merge. The exact squash-merged
`main` SHA must then receive the same local release gate before publication.

## Security Reporting Disposition

The branch now uses GitHub private vulnerability reporting through the Security
tab. It no longer publishes an unverified mailbox, PGP fingerprint, or fixed
response-time promise. Sensitive vulnerability details must not be posted in
public issues, discussions, or pull requests.

## Objective

Verify that a fresh checkout can install tooling, pass strict quality and
security checks, validate adapter inventory behavior, execute packaged CLI smoke
workflows, and prove raw-log report redaction before public-beta visibility.

## Required Validation Setup

Use a clean disposable clone or worktree. On Windows, place pytest's temporary
base outside the repository to avoid ACL and stale-directory artifacts.

Representative setup:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev,helpers]"
python -m pip check
$base = Join-Path $env:TEMP "zscripts-pytest-$([guid]::NewGuid())"
```

## Required Source-Tree Gate

```sh
python scripts/bootstrap.py --print-only
ruff format --check .
ruff check .
python scripts/no_binaries.py
python -m pytest -q --basetemp="$base"
python scripts/validate_docs_links.py
git diff --check
mypy zscripts/application zscripts/config.py zscripts/configuration.py zscripts/observability/logging.py zscripts/observability/metrics.py zscripts/observability/health.py zscripts/observability/instrumentation.py zscripts/extensions/scaffolding.py zscripts/schemas
python -m coverage erase
python -m coverage run -m pytest --basetemp="$base"
python -m coverage report --fail-under=85
python -m coverage json -o reports/coverage.json
python -m bandit -q -r zscripts examples/sample_project
python -m pip_audit
pre-commit run --all-files
```

If GNU Make is available, also run `make check`; the individual commands above
remain authoritative.

## Editable-Installation Smoke

From a directory outside the repository checkout:

```sh
python -c "import zscripts; print(zscripts.__file__)"
zscripts guardrails
python -m zscripts guardrails
zscripts adapters --format json
```

The adapter identifiers must be deterministic:

```text
ci
docker
dotnet
go
java
javascript
python
rust
```

## Wheel Gate

```sh
python -m build --wheel --outdir dist
```

Create a separate clean virtual environment, install only the generated wheel,
change to a directory outside the repository, and run:

```sh
python -c "import zscripts; print(zscripts.__file__)"
zscripts guardrails
python -m zscripts guardrails
zscripts adapters --format json
```

The repository root and `PYTHONPATH=.` must not mask missing wheel content.

## Zipapp, Diagnostics, and Redaction Gate

```sh
python scripts/build_artifact.py
python artifacts/build/zscripts.pyz guardrails
python artifacts/build/zscripts.pyz adapters --format json
python -m scripts.diagnostics_probe --include-metrics --output reports/diagnostics_local.json --fail-on-status degraded
python cli.py --adapter ci report --input examples/raw_to_report/raw.log --format markdown --redact --output artifacts/build/raw_to_report_demo.md
```

Confirm that the diagnostics output is valid JSON and that the generated report
does not expose the complete fixture value, common provider-token forms, API
keys, passwords, bearer tokens, or organization-specific secrets.

## Secret-Scanning Gate

```sh
gitleaks detect --no-git --source . --redact --verbose
gitleaks detect --source . --redact --verbose
```

Both the tracked-worktree and full-history scans must execute successfully. Record
the history commit count.

## Configuration Parsing

Use real parsers to validate at minimum:

- `.github/workflows/ci.yml`
- `.github/dependabot.yml`
- `.pre-commit-config.yaml`
- `.gitleaks.toml`
- `pyproject.toml`

## Historical PR #47 Results

| Check | Result |
| --- | --- |
| Install | Pass (`python -m pip install -e .[dev,helpers]`) |
| Format | Pass (`ruff format --check .`) |
| Lint | Pass (`ruff check .`) |
| Binary scan | Pass (`python scripts/no_binaries.py`) |
| Tests | Pass (`176 passed, 13 warnings`) |
| Documentation links | Pass (`python scripts/validate_docs_links.py`) |
| Diff whitespace | Pass (`git diff --check`) |
| Type checks | Pass (supported mypy surface) |
| Coverage | Pass (92%, threshold 85%) |
| Build | Pass (`python scripts/build_artifact.py`) |
| Packaged guardrails smoke | Pass |
| Packaged adapter inventory smoke | Pass |
| Raw-log-to-report demo | Pass |
| Report redaction scan | Pass |
| Bandit | Pass under Python 3.14.0 |
| Dependency audit | Pass (`python -m pip_audit`) |
| Gitleaks tracked-file scan | Pass |
| Gitleaks full-history scan | Pass |

## Publication Sequence

1. Validate the exact latest PR #48 head locally.
2. Record the exact SHA, commands, exit codes, test count, coverage, packaging,
   security, redaction, and Gitleaks results.
3. Confirm hosted CI passes on the same final branch head.
4. Mark PR #48 ready, review, and squash-merge with expected-head protection.
5. Repeat the complete gate on the exact merged `main` SHA.
6. Confirm a clean worktree.
7. Change visibility to public.
8. Rerun CI and enable or verify private vulnerability reporting, secret scanning,
   push protection, Dependabot security features, and CodeQL where eligible.
9. Review initial alerts before describing the repository as clean or stable.
