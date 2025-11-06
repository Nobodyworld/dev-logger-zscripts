# Security Notes

## Vulnerability Scans
- `make security` failed because `bandit` is not installed in the execution
  environment. Install `bandit>=1.7.10` (included in `pyproject.toml` dev extras)
  before running the scan.

## Secrets Handling
- All configuration secrets are expected to flow through configuration files or
  environment variables; no hard-coded secrets were detected during the audit.

## Remediation Summary
- Publish an internal mirror or pre-bundle wheels so the security scan can run in
  network-restricted sandboxes.
