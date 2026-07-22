# Dependency Audit

Last reviewed: 2026-07-21

| Package | Version Constraint | Purpose | License | Notes |
|---------|--------------------|---------|---------|-------|
| jsonschema | `>=4.21,<5` | Validates normalized log payloads against the shipped schema. | MIT | Required core runtime dependency; validation never silently disables itself. |
| setuptools | `>=83.0.0` | Builds packages and supports the development toolchain. | MIT | Build/development constraint includes the fix for `PYSEC-2026-3447`. |
| pytest | `>=7.0` | Executes the unit test suite. | MIT | Developer dependency only. |
| ruff | `>=0.6.9` | Formatting and linting. | MIT | Developer dependency. |
| mypy | `>=1.11.2` | Static type checking on the supported surface. | MIT | Developer dependency. |

## Evaluation Summary

- **Runtime footprint** is intentionally minimal: only `jsonschema` is required.
  Package installation brings it in directly, and invalid normalized payloads
  raise `jsonschema.ValidationError` instead of bypassing validation.
- **Development tooling** is lightweight and pinned to modern releases to ensure
  compatibility with Python 3.14.
- **Transitive dependencies** are resolved and checked by `pip-audit`; the
  hosted gate audits the installed development and helper environment.

## Policy

1. Audit dependencies quarterly and after major security advisories.
2. Document rationale for any new dependency in this file and link supporting
   ADRs if the change affects architecture or governance.
3. Use `make sbom` (when available) to generate CycloneDX manifests for release
   candidates and attach them to build artifacts.
4. Prefer standard library solutions unless a third-party dependency materially
   reduces risk or effort.
