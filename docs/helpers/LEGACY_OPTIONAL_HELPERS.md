# Legacy and Optional Helpers

The strict project identity is:

**Cross-language log normalization and diagnostic CLI**

The `zscripts/helpers` package is outside strict core scope and is therefore:

- Legacy: maintained for compatibility with existing automation.
- Optional: installed via extras only (`helpers`, `helpers-web`, `helpers-ml`).

## Policy

- New core features should land in adapters, services, schemas, and CLI layers.
- Helper additions require clear justification and tests.
- Helper domains should be migrated to a separate repository over time.

## Migration Direction

When splitting helper domains out:

1. Preserve existing import paths via compatibility shims where practical.
2. Pin helper dependencies in the new repository for reproducibility.
3. Keep this repository focused on normalization, diagnostics, and reporting.
