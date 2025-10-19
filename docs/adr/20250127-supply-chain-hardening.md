# ADR 20250127: Supply Chain Hardening Baseline

## Status
Accepted

## Context
The initial modernization pass introduced governance and CI but lacked supply-chain protections. Developers had no turnkey way to produce a software bill of materials (SBOM), and neither local hooks nor CI scanned for committed secrets. Given the CLI operates on customer repositories, leaking credentials or shipping unsigned dependencies poses a high operational risk.

## Decision
1. Add a `make sbom` target backed by `cyclonedx-py` to emit JSON and XML manifests under `artifacts/sbom/`, and publish the artifacts in CI.
2. Extend pre-commit with `detect-secrets` using `.secrets.baseline` so contributors run lightweight secret scans before pushing.
3. Run `gitleaks` in GitHub Actions with `.gitleaks.toml` to provide a second enforcement layer without requiring local installation.

## Consequences
- Contributors must maintain `.secrets.baseline` when adding fixtures that resemble credentials.
- CI emits SBOM artifacts for every Python 3.11 build, enabling downstream dependency audits.
- Secret scanning failures will block merges; documentation now explains remediation.
- `cyclonedx-bom` becomes a development dependency and must remain up to date via Renovate or manual bumps.
