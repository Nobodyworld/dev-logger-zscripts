# Legacy and Optional Helpers

The strict project identity is:

**Cross-language log normalization and diagnostic CLI**

The `zscripts/helpers` package is outside strict core scope and is therefore:

- Legacy: maintained for compatibility with existing automation.
- Optional: installed via extras only (`helpers`, `helpers-web`, `helpers-ml`).

Phase 2A freezes all 154 tracked helper Python modules in the wheel. Seven
registry-exposed modules are temporary import/registry compatibility points;
their current behavior is not declared production-supported. All other modules
are legacy, unsupported, and temporarily wheel-included. The enforceable policy
is recorded in
[`../operations/LEGACY_HELPER_COMPATIBILITY.md`](../operations/LEGACY_HELPER_COMPATIBILITY.md).

## Policy

- New core features should land in adapters, services, schemas, and CLI layers.
- Helper additions require clear justification and tests.
- Helper domains should be migrated to a separate repository over time.
- Maintained core layers must not import `zscripts.helpers` or obsolete
  top-level `helpers` paths.

## Migration Direction

When splitting helper domains out:

1. Preserve existing import paths via compatibility shims where practical.
2. Pin helper dependencies in the new repository for reproducibility.
3. Keep this repository focused on normalization, diagnostics, and reporting.

No Phase 2B migration can begin until at least 90 days after the Phase 2A merge
and at least one documented public-beta deprecation cycle have completed,
whichever is later. Consumer review and separate owner approval are still
required after that threshold. Torch remains at 2.9.0; Torch 2.13 review is
deferred to the ML-helper decision under issue #62.
