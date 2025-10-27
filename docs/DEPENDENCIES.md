# Dependency Audit

Last reviewed: 2025-10-19

| Package | Version Constraint | Purpose | License | Notes |
|---------|--------------------|---------|---------|-------|
| jsonschema | `>=4.21` | Validates normalized log payloads against the shipped schema. | MIT | Required at runtime. Consider pinning for reproducibility. |
| pytest | `>=7.4` | Executes the unit test suite. | MIT | Developer dependency only. |
| ruff | `>=0.2` | Formatting and linting. | MIT | Developer dependency. |
| mypy | `>=1.8` | Static type checking in strict mode. | MIT | Developer dependency. |

## Evaluation Summary

- **Runtime footprint** is intentionally minimal: only `jsonschema` is required.
  The service now surfaces clear errors when validation is unavailable, so keep
  the dependency installed in production environments.
- **Development tooling** is lightweight and pinned to modern releases to ensure
  compatibility with Python 3.14.
- **Transitive dependencies**: `jsonschema` depends on `attrs`, `pyrsistent`,
  and `referencing` (all permissive licenses). No known CVEs affect the pinned
  range as of the review date.

## Policy

1. Audit dependencies quarterly and after major security advisories.
2. Document rationale for any new dependency in this file and link supporting
   ADRs if the change affects architecture or governance.
3. Use `make sbom` (when available) to generate CycloneDX manifests for release
   candidates and attach them to build artifacts.
4. Prefer standard library solutions unless a third-party dependency materially
   reduces risk or effort.
