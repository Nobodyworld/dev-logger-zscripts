# Legacy Helper Phase 2A Compatibility Contract

Status: owner-approved Phase 2A contract from issue #70. Phase 2B is not
authorized.

The follow-up
[`consumer and ownership review`](LEGACY_HELPER_CONSUMER_REVIEW.md) records
current, historical, and indexed-public evidence. The
[`public-beta deprecation notice`](LEGACY_HELPER_DEPRECATION_NOTICE.md) records
the merged start event and begins—but does not complete—the mandatory cycle.

## Scope

Phase 2A is non-breaking preparation for issue #62. It freezes the complete
tracked helper surface, identifies temporary compatibility points, and prevents
maintained core code from acquiring helper dependencies. It does not remove,
move, rename, repair, modernize, or execute helper modules. It does not change
package discovery or helper behavior.

All **154 tracked Python modules** under `zscripts/helpers` remain temporarily
included in the wheel. The deterministic baseline is
[`legacy_helper_surface.json`](legacy_helper_surface.json), and the reviewed
machine-readable contract is
[`legacy_helper_compatibility.json`](legacy_helper_compatibility.json).

## Public contract

Seven registry-exposed modules are temporary import/registry compatibility
points. This protects their current module paths, registry keys, and callable
names during the compatibility window. It does **not** declare their behavior
production-supported, safe for unreviewed input, or stable as an API.

Every other helper module has one default policy:

> legacy / unsupported / temporarily wheel-included

No executing compatibility shim is added in Phase 2A. The `phase2b_proposal`
values below are review directions only; they do not approve migration,
retirement, shims, packaging exclusion, or any other Phase 2B action.

## Temporary compatibility points

All owners remain `unassigned` until the owner explicitly records an approved
maintainer identifier.

| Module | Registry keys | Callables | Risk | Phase 2B proposal |
| --- | --- | --- | --- | --- |
| `zscripts.helpers.numpy.array_utils` | `numpy.batched`, `numpy.normalize_columns`, `numpy.rolling_window` | `batched`, `normalize_columns`, `rolling_window` | moderate | migrate |
| `zscripts.helpers.pandas.concat_csvs` | `pandas.concat_csvs` | `consolidate_files` | critical-review | retire-review |
| `zscripts.helpers.pandas.excel_to_json_posts` | `pandas.excel_to_json_posts` | `process_excel_file` | moderate | migrate |
| `zscripts.helpers.pillow.add_watermark` | `pillow.add_watermark` | `add_watermark` | moderate | migrate |
| `zscripts.helpers.pillow.ratio_image_2` | `pillow.resize_by_aspect`, `pillow.resize_by_ratio` | `resize_images_by_aspect_ratio`, `resize_images_by_ratio` | high | retire-review |
| `zscripts.helpers.requests.http` | `requests.fetch_json`, `requests.retrying_session` | `create_retrying_session`, `fetch_json` | high | retire-review |
| `zscripts.helpers.web_crawl.html_ops` | `html_ops.bold_prefix`, `html_ops.listify`, `html_ops.section` | `bold_li_prefix_before_colon`, `listify_numbered_paragraphs`, `section_by_h2` | moderate | migrate |

The NumPy and Requests package-level re-exports and the documented registry
entry point are compatibility evidence, not broader behavioral support. Static
risk and dependency evidence comes from the merged
[`legacy_helper_inventory.json`](legacy_helper_inventory.json). Registry targets
are parsed but never imported or executed by the boundary checks.

## Compatibility window

The window begins only when Phase 2A merges. Phase 2B cannot begin until both of
the following have completed:

1. at least 90 calendar days have elapsed after the Phase 2A merge; and
2. at least one documented public-beta deprecation cycle has completed.

The later condition controls. No fixed Phase 2B calendar date can be calculated
or published before the merge event. The merge and threshold are now recorded
in the deprecation notice, but that threshold is not a Phase 2B authorization
date. After the window, Phase 2B still requires consumer review and separate
owner approval. Passing the eligibility threshold does not authorize removal or
extraction automatically.

This is a public-source compatibility commitment for the public beta. It is not
a stable-release semantic-version guarantee and does not convert the legacy
helper collection into a supported public package.

## Enforced package boundary

Maintained runtime code in these scopes may not import either
`zscripts.helpers...` or obsolete top-level `helpers...` paths:

- `zscripts/application`
- `zscripts/domain`
- `zscripts/infrastructure`
- `zscripts/observability`
- `zscripts/extensions`
- `zscripts/schemas`
- `adapters`
- `agents`

`scripts/check_legacy_helper_boundary.py` uses tracked-file enumeration, JSON
validation, AST parsing, and wheel member inspection. It never imports helper
source. The canonical quality gate exposes `helper-surface`, `helper-boundary`,
and `helper-compatibility` operations. Hosted CI runs them inside the existing
`quality` job; no second status context is introduced.

## Surface expansion policy

Adding a tracked helper module requires an intentional baseline update and an
owner-approved security or compatibility exception. A baseline module may not
disappear during Phase 2A. Duplicate, unsorted, absolute, missing, or untracked
paths fail the gate.

## Torch freeze

Phase 2A preserves `torch==2.9.0` in the ML requirements and the existing
`torch>=2.9.0` package-metadata lower bound. Torch 2.13 remains deferred. Torch
review belongs to the ML-helper migration/disposition decision under issue #62;
no Torch upgrade is authorized during Phase 2A.

## Phase 2B prerequisites

Before any Phase 2B proposal can be approved, the owner must record consumer
review results, assign maintainers or explicitly accept unowned retirement risk,
choose any non-executing compatibility shims, review dependency/security and
platform support, and approve the final packaging change. Phase 2A performs none
of those changes.
