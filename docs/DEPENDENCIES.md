# Dependency Audit

Last reviewed: 2026-07-24

| Package | Version Constraint | Purpose | License | Notes |
|---------|--------------------|---------|---------|-------|
| jsonschema | `>=4.21,<5` | Validates normalized log payloads against the shipped schema. | MIT | Required core runtime dependency; validation never silently disables itself. |
| setuptools | `>=83.0.0` | Builds packages and supports the development toolchain. | MIT | Build/development constraint includes the fix for `PYSEC-2026-3447`. |
| pytest | `>=7.0` | Executes the unit test suite. | MIT | Developer dependency only. |
| ruff | `==0.15.22` | Formatting and linting. | MIT | Exact developer pin preserves a reviewed formatter contract. Ruff upgrades require a focused compatibility and formatting PR. |
| mypy | `>=1.11.2` | Static type checking on the supported surface. | MIT | Developer dependency only. |

## Evaluation Summary

- **Runtime footprint** is intentionally minimal: only `jsonschema` is required.
  Package installation brings it in directly, and invalid normalized payloads
  raise `jsonschema.ValidationError` instead of bypassing validation.
- **Development tooling** is lightweight and pinned where tool output forms part
  of the required repository contract. Ruff is exact-pinned because formatter
  releases can change required diffs and otherwise make hosted CI non-reproducible.
- **Transitive dependencies** are resolved and checked by `pip-audit`; the
  hosted gate audits the installed development and helper environment.

## Tool Upgrade Policy

Formatter and linter upgrades must be delivered through a focused pull request
that:

1. updates every active declaration of the tool version;
2. runs the formatter explicitly and reviews the resulting diff;
3. validates lint, tests, packaging, and the complete hosted `quality` gate; and
4. records the new reviewed exact pin.

Do not allow a required formatter contract to change implicitly because a newer
release appeared on the package index.

## Policy

1. Audit dependencies quarterly and after major security advisories.
2. Document rationale for any new dependency in this file and link supporting
   ADRs if the change affects architecture or governance.
3. Use `make sbom` (when available) to generate CycloneDX manifests for release
   candidates and attach them to build artifacts.
4. Prefer standard library solutions unless a third-party dependency materially
   reduces risk or effort.
