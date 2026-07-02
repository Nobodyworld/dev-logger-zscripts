# Security Notes

## Vulnerability Scans

- Historical note: an older sandbox run failed because `bandit` was missing.
- Current authoritative clean-clone validation (2026-07-01) confirms:
  - `bandit -q -r zscripts examples/sample_project` passes.
  - `pip-audit -r requirements.txt` reports no known vulnerabilities.
  - `python scripts/no_binaries.py` passes.

## Secrets Handling

- Full-history equivalent secret scan (`detect-secrets` over git patch history)
  found no results in repository history material.
- HEAD tracked-file scan reported keyword hits in
  `examples/sample_project/infra/docker-compose.yml`; these are example fixture
  placeholders, not active credentials.

## Remediation Summary

- Keep secret scanning focused on tracked repository files (exclude virtual
  environments and caches in local scans).
- Continue to route sensitive runtime values through environment variables or
  secure external stores.
