# Dependency Audit

Last reviewed: 2026-07-24

| Package | Version Constraint | Purpose | License | Notes |
|---------|--------------------|---------|---------|-------|
| jsonschema | `>=4.21,<5` | Validates normalized log payloads against the shipped schema. | MIT | Required core runtime dependency; validation never silently disables itself. |
| setuptools | `>=83.0.0` | Builds packages and supports the development toolchain. | MIT | Build/development constraint includes the fix for `PYSEC-2026-3447`. |
| pytest | `>=7.0` | Executes the unit test suite. | MIT | Developer dependency only. |
| ruff | `==0.15.22` | Formatting and linting. | MIT | Exact developer pin preserves a reviewed formatter contract. Ruff upgrades require a focused compatibility and formatting PR. |
| mypy | `>=1.11.2` | Static type checking on the supported surface. | MIT | Developer dependency only. |
| FastAPI | `==0.139.2` | Experimental same-origin localhost API and static workspace server. | MIT | Workspace extra only; no remote deployment is supported by the MVP. |
| Pydantic | `==2.13.4` | Strict request/response validation for experimental routes. | MIT | Workspace extra only. |
| Uvicorn | `==0.51.0` | Loopback ASGI server for `zscripts workspace`. | BSD-3-Clause | Workspace extra only; the CLI rejects non-`127.0.0.1` binding. |
| HTTPX2 | `==2.9.1` | Current Starlette/FastAPI `TestClient` transport. | BSD-3-Clause | Developer dependency only. |
| types-jsonschema | `==4.26.0.20260518` | Strict mypy stubs for the required JSON Schema runtime. | Apache-2.0 | Developer dependency only. |

## Repository-review frontend

The frontend is private package-manager input; only its generated production
assets are copied into the Python wheel. Every direct package is exact-pinned in
`workspace-ui/package.json` and the complete transitive graph is frozen by
`pnpm-lock.yaml`.

| Direct package | Version | Purpose | License |
| --- | --- | --- | --- |
| React / React DOM | `19.2.8` | Production UI/runtime rendering. | MIT |
| Vite / `@vitejs/plugin-react` | `8.1.5` / `6.0.4` | Production asset build. | MIT |
| TypeScript | `6.0.3` | Static frontend types. | Apache-2.0 |
| Vitest / jsdom | `4.1.10` / `29.1.1` | Browser-like unit and interaction tests. | MIT |
| Testing Library React / user-event | `16.3.2` / `14.6.1` | Accessible component interaction tests. | MIT |
| ESLint / `@eslint/js` | `10.7.0` / `10.0.1` | JavaScript/TypeScript linting. | MIT |
| typescript-eslint | `8.65.0` | TypeScript ESLint integration. | MIT |
| React Hooks / Refresh ESLint plugins | `7.1.1` / `0.5.3` | React lint contracts. | MIT |
| Prettier | `3.9.6` | Deterministic frontend formatting. | MIT |
| globals | `17.7.0` | Lint environment definitions. | MIT |
| React / React DOM type packages | `19.2.17` / `19.2.3` | TypeScript declarations. | MIT |

The production bundle's React/React DOM MIT notice is retained in
`workspace-ui/THIRD_PARTY_NOTICES.md` and copied into wheel package data. Build
and test tools are not imported by or shipped as Python runtime dependencies.
`pnpm licenses list` is the review command for the full transitive frontend
license inventory.

## CI action provenance

The new Node setup action remains immutable commit-pinned:

| Action | Commit | Reviewed tag |
| --- | --- | --- |
| `actions/setup-node` | `48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e` | `v6.4.0` |

The workflow activates exact `pnpm@10.18.1` through the Corepack bundled with
the selected Node runtime. This avoids an unapproved third-party action while
retaining deterministic package-manager activation under the repository's
existing Actions allowlist.

Existing checkout, Python setup, and artifact-upload actions remain pinned to
their previously reviewed commits.

## Evaluation Summary

- **Runtime footprint** is intentionally minimal: only `jsonschema` is required.
  Package installation brings it in directly, and invalid normalized payloads
  raise `jsonschema.ValidationError` instead of bypassing validation.
- **Workspace dependencies** are isolated behind the optional `workspace` extra.
  FastAPI/Pydantic/Uvicorn are imported lazily, so the standard CLI still imports
  and runs when that extra is absent.
- **Frontend runtime** adds only React and React DOM. The build/test stack is
  exact-pinned, lockfile-frozen, license-reviewed, and absent from the Python
  runtime dependency graph.
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
