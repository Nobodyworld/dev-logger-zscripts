# Security Policy

## Supported Versions
| Version | Supported |
|---------|-----------|
| main    | ✅
| Releases < 0.2.0 | ⚠️ Best-effort security fixes only |

## Reporting a Vulnerability
- Email `security@zscripts.dev` with a clear description, reproduction steps, and impact analysis.
- Encrypt sensitive details using our PGP key (`security@zscripts.dev`, fingerprint `B4C9 2EAF 2A92 91E1 78AC  114A 3AA0 45B9 5D5B 3E10`).
- We acknowledge reports within **48 hours** and provide a remediation plan within **7 calendar days**.
- Please do not open public issues for security reports.

## Handling Process
1. Triage, reproduce, and assign a severity (CVSS v3.1).
2. Develop and test a fix on a private branch, including regression tests.
3. Coordinate disclosure timeline with reporter; default disclosure window is 30 days.
4. Publish advisory, update CHANGELOG, and tag a patched release.

## Security Tooling
- Bandit, mypy (strict), Ruff, and pytest run in CI for every change.
- Upcoming additions: SBOM generation, dependency and secret scanning, Renovate automation.
- Dependency posture is tracked in `docs/DEPENDENCIES.md`; review quarterly or after major advisories.

## Responsible Disclosure
We appreciate coordinated disclosure and are happy to credit researchers unless anonymity is requested.
