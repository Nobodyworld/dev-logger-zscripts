# Technical Debt Backlog

## P1
- Provision an internal mirror or vendored wheels so `make setup` and `make security`
  can install `setuptools`, `bandit`, and other extras in network-restricted
  environments.

## P2
- Add an automated secret-scanning step (e.g., `gitleaks`) alongside the existing
  quality gate to catch committed secrets.
- Extend the build pipeline to exercise the zipapp artifact with an integration
  test that covers a non-trivial command (e.g., `report`) against fixture data.

## P3
- Capture authoritative license information for tooling such as Ruff to replace
  the missing metadata in the generated baseline report.
