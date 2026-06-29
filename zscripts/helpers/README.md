# Helpers

This package bundles ready-to-use helpers across data processing, APIs, and
automation domains. Modules are grouped by technology (for example `pandas/`,
`numpy/`, `web_crawl/`) so they can be consumed independently.

Status: legacy and optional. The strict project identity is
cross-language log normalization and diagnostics; helper modules are retained
for backwards compatibility and may move to a dedicated repository.

## Usage

- Import helpers directly from the corresponding subpackage, e.g.
  `from helpers.numpy.linalg import stable_det`.
- Extensions that register custom behaviours must be declared in
  `helpers/registry.py` and, when applicable, in `configs/registry.yaml`.
- Each domain links to deep-dive notes in [`docs/helpers/`](../docs/helpers/).

When introducing a new helper module, create a README inside its subdirectory if
the usage is non-obvious and add regression coverage under `tests/`.
