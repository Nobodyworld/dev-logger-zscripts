# Legacy Helper Consumer and Ownership Review

Status: complete consumer evidence for issue #73. This review supports issue
#62, starts the public-beta deprecation cycle, and does **not** authorize or
begin Phase 2B.

The deterministic evidence record is
[`legacy_helper_consumers.json`](legacy_helper_consumers.json). The public
notice is
[`LEGACY_HELPER_DEPRECATION_NOTICE.md`](LEGACY_HELPER_DEPRECATION_NOTICE.md).

## 1. Audited revision and exact-main CI

This review started from exact SHA
`d3a4eb92ed7f4f1590e7f4ea3ae079edb15a7d35` on
`docs/legacy-helper-consumer-review`.

The required merged-main verification passed:

- Workflow: `CI`
- Run: [`29969757407`](https://github.com/Nobodyworld/dev-logger-zscripts/actions/runs/29969757407)
- Event: `push`
- Head branch: `main`
- Head SHA: `d3a4eb92ed7f4f1590e7f4ea3ae079edb15a7d35`
- Job: `quality` (`89089004580`)
- Run and job conclusion: `success`

The `Legacy helper Phase 2A contracts` step and every normal quality step
executed successfully: installation, Ruff lint, mypy, Bandit, dependency audit,
binary scan, tests with coverage, documentation links, editable install, wheel,
zipapp, diagnostics, and artifact upload.

## 2. Methodology

The review never imported or executed helper source. It used:

1. the registry, Phase 2A compatibility manifest, inventory JSON, and their
   narratives as authoritative starting evidence;
2. tracked-file exact-string and regex searches for all seven module paths, all
   13 registry keys, and all declared callables;
3. separate classification of direct imports, package re-exports, registry
   references, direct invocations, test-only references, documentation-only
   references, and scopes with no current reference;
4. full reachable Git-history `-S` string and `-G` regex searches, followed by
   relevant file history and commit diff inspection; and
5. authenticated GitHub code search for each full module path, each registry
   key, and each distinctive full-path import form, with a limit of 100 results
   per query.

The current search included tests, examples, documentation, workflows,
configuration, automation, and scripts. Same-name symbols were not accepted as
consumers without module, import, registry, or call-site context.

## 3. Search limitations

- GitHub code search covers indexed public code. It can omit private, deleted,
  archived, unindexed, non-default-branch, or otherwise unavailable content.
- “No indexed public match found” is not a claim that no external consumer
  exists.
- The reachable Git history receives the helper collection in the single
  `05c62dc38955a05cc422ae015e078d4450f339d5` consolidation commit. It cannot
  establish provenance or consumers in the source repository before that
  import.
- Exact callable searches produced unrelated homonyms. In particular, the core
  `zscripts.utils.consolidate_files` and the historical operations
  `_fetch_json` function are unrelated to these compatibility points.
- External repositories were not cloned or executed. No credentials or
  sensitive user data were sought.

## 4. Consumer summary

| Compatibility point | Current non-test evidence | Public external evidence | Proposal |
| --- | --- | --- | --- |
| `zscripts.helpers.numpy.array_utils` | Package re-export only; no independent runtime consumer found | No indexed external consumer match | migrate |
| `zscripts.helpers.pandas.concat_csvs` | Guarded self-invocation only; no independent runtime consumer found | No indexed external consumer match | retire-review |
| `zscripts.helpers.pandas.excel_to_json_posts` | Guarded self-invocation only; no independent runtime consumer found | No indexed external consumer match | migrate |
| `zscripts.helpers.pillow.add_watermark` | Obsolete-path import and invocation in `thumb_wm_marg.py`; README registry example | No indexed external consumer match | migrate |
| `zscripts.helpers.pillow.ratio_image_2` | No independent runtime consumer found | No indexed external consumer match | retire-review |
| `zscripts.helpers.requests.http` | Package re-export and internal callable coupling; no independent runtime consumer found | No indexed external consumer match | retire-review |
| `zscripts.helpers.web_crawl.html_ops` | Three helper-internal wrappers import and invoke the compatibility callables | No indexed external consumer match | migrate |

Registry entries are compatibility surfaces, not runtime-consumer proof.
Contract scripts and narratives are evidence records, not runtime consumers.

## 5. Current internal consumers

### `zscripts.helpers.numpy.array_utils`

No non-test runtime consumer was found outside the compatibility module and its
package re-export. `tests/test_numpy_helpers.py` imports `batched`,
`normalize_columns`, and `rolling_window` from `zscripts.helpers.numpy` and
invokes each.

### `zscripts.helpers.pandas.concat_csvs`

No independent runtime consumer was found. The guarded `main()` inside the same
module invokes `consolidate_files` for organization-specific paths. The
same-named core utility and captured example-log references have a different
signature and lineage and are not consumers of this module.

### `zscripts.helpers.pandas.excel_to_json_posts`

No independent runtime consumer was found. The guarded `main()` inside the same
module invokes `process_excel_file` and writes JSON.

### `zscripts.helpers.pillow.add_watermark`

`zscripts/helpers/pillow/thumb_wm_marg.py` imports the callable through the
obsolete `helpers.pillow.add_watermark` path and invokes it in batch image
automation. That module has import-time filesystem traversal, writes, and
deletion behavior. This is real internal compatibility pressure, but not a safe
or stable public-interface signal.

### `zscripts.helpers.pillow.ratio_image_2`

No non-test runtime consumer was found outside the compatibility module.

### `zscripts.helpers.requests.http`

No independent runtime consumer was found outside the module and package
re-export. Within the module, `fetch_json` invokes `create_retrying_session` when
the caller does not supply a session.

### `zscripts.helpers.web_crawl.html_ops`

Three helper-internal wrappers are direct consumers:

- `zscripts/helpers/web_crawl/list_from.py` imports and invokes
  `listify_numbered_paragraphs` and `bold_li_prefix_before_colon`;
- `zscripts/helpers/web_crawl/sections.py` imports and invokes `section_by_h2`;
  and
- `zscripts/helpers/web_crawl/strong.py` imports and invokes
  `bold_li_prefix_before_colon`.

## 6. Historical consumers, removals, and renames

All seven module files, all 13 registry targets, the focused tests, both package
re-exports, and the known helper-internal consumers first appear in
`05c62dc38955a05cc422ae015e078d4450f339d5`, “Consolidate
dev-scripts-zhelpers into zscripts.”

No removed consumer, renamed compatibility module, or renamed declared callable
was found in reachable history. The later changes to
`pandas/concat_csvs.py` and `pillow/ratio_image_2.py` were import-order or
formatting changes, not consumer changes.

History suggests:

- NumPy and Requests were deliberately exposed as narrow reusable interfaces
  through package re-exports, registry keys, and focused pytest coverage.
- The Pandas and Pillow points arrived as file-oriented or batch-oriented
  internal tooling with standalone smoke scripts.
- `html_ops` is a durable internal workflow boundary because three sibling
  wrappers consume it.
- Registry exposure establishes temporary compatibility, but none of these
  signals establishes a stable public API or production support contract.

Obsolete top-level evidence remains:

- `zscripts.helpers.pandas.concat_csvs` imports `helpers.utilities.paths`; and
- `zscripts/helpers/pillow/thumb_wm_marg.py` imports
  `helpers.pillow.add_watermark`.

This review does not repair either path or restore any deleted content.

## 7. Public GitHub search evidence

Every full module-path query returned only
`Nobodyworld/dev-logger-zscripts`, specifically the Phase 2A compatibility JSON,
inventory JSON, and contract script. Registry-key queries likewise returned
only this repository, except for the reviewed false positives below. Every
distinctive `from zscripts.helpers... import` query returned no indexed public
match.

The exact `requests.fetch_json` registry-key query also returned three files in
`duriantaco/skylos`:

- [`benchmarks/ai_code_defects/manifest.json`](https://github.com/duriantaco/skylos/blob/a3b345f9be9196c8d866274d4fe73f25737df39d/benchmarks/ai_code_defects/manifest.json)
- [`test/test_ai_code_defect_benchmark.py`](https://github.com/duriantaco/skylos/blob/a3b345f9be9196c8d866274d4fe73f25737df39d/test/test_ai_code_defect_benchmark.py)
- [`test/test_ai_defect_challenge_harness.py`](https://github.com/duriantaco/skylos/blob/a3b345f9be9196c8d866274d4fe73f25737df39d/test/test_ai_defect_challenge_harness.py)

Those matches describe the unrelated third-party `requests` package *not*
exposing `requests.fetch_json`. They do not import or invoke `zscripts` and are
recorded as external non-consumer matches. Both repositories reported
`isFork: false`; no duplicate or fork consumer remained after review.

Result for every compatibility point: **no indexed public external consumer
match found**.

## 8. Registry-key evidence

`configs/registry.yaml` contains exactly 13 entries across exactly seven target
modules:

| Key | Target |
| --- | --- |
| `html_ops.bold_prefix` | `zscripts.helpers.web_crawl.html_ops:bold_li_prefix_before_colon` |
| `html_ops.listify` | `zscripts.helpers.web_crawl.html_ops:listify_numbered_paragraphs` |
| `html_ops.section` | `zscripts.helpers.web_crawl.html_ops:section_by_h2` |
| `numpy.batched` | `zscripts.helpers.numpy.array_utils:batched` |
| `numpy.normalize_columns` | `zscripts.helpers.numpy.array_utils:normalize_columns` |
| `numpy.rolling_window` | `zscripts.helpers.numpy.array_utils:rolling_window` |
| `pandas.concat_csvs` | `zscripts.helpers.pandas.concat_csvs:consolidate_files` |
| `pandas.excel_to_json_posts` | `zscripts.helpers.pandas.excel_to_json_posts:process_excel_file` |
| `pillow.add_watermark` | `zscripts.helpers.pillow.add_watermark:add_watermark` |
| `pillow.resize_by_aspect` | `zscripts.helpers.pillow.ratio_image_2:resize_images_by_aspect_ratio` |
| `pillow.resize_by_ratio` | `zscripts.helpers.pillow.ratio_image_2:resize_images_by_ratio` |
| `requests.fetch_json` | `zscripts.helpers.requests.http:fetch_json` |
| `requests.retrying_session` | `zscripts.helpers.requests.http:create_retrying_session` |

The only exact registry call outside the registry implementation is the
README’s `call("pillow.add_watermark", ...)` example. It is documentation-only
evidence. No repository runtime registry call was found.

## 9. Package re-export evidence

Two package re-export surfaces exist:

- `zscripts/helpers/numpy/__init__.py` re-exports `batched`,
  `normalize_columns`, and `rolling_window`; and
- `zscripts/helpers/requests/__init__.py` re-exports
  `create_retrying_session` and `fetch_json`.

No package re-export was found for either Pandas module, either Pillow module,
or `web_crawl.html_ops`.

## 10. Tests and documentation

- `tests/test_numpy_helpers.py` is pytest-collected and invokes all three NumPy
  callables through the package re-export.
- `tests/test_requests_helpers.py` is pytest-collected and exercises both
  Requests callables with mocked HTTP behavior.
- `tests/smoke_pandas_concat_csvs.py`,
  `tests/smoke_pandas_excel_to_json_posts.py`,
  `tests/smoke_pillow_watermark_ratio.py`, and
  `tests/smoke_web_crawl_html_ops.py` directly import and invoke their helpers,
  but their `smoke_` names are not collected by default pytest discovery.
- The Phase 2A compatibility narrative documents all seven points.
- The README documents only the `pillow.add_watermark` registry call.
- The inventory associates `html_ops` with two broad crawler-domain documents;
  neither names the declared compatibility callables, so neither is behavioral
  support evidence.

## 11. Dependency, platform, security, and import-time constraints

| Point | Imports | Static/import-time constraints |
| --- | --- | --- |
| NumPy | `numpy` | Moderate dependency/platform risk; no classified import-time executable statement |
| Pandas CSV | `pandas` | Critical-review; imports obsolete organization-path code; top-level logger initialization |
| Pandas Excel | `pandas` | Moderate; Excel-engine/file-format behavior; top-level logger initialization |
| Pillow watermark | `PIL` | Moderate; reads input/logo/font resources when invoked; internal consumer is destructive import-time automation |
| Pillow ratio | `PIL` | High; reads and writes images and creates directories when invoked |
| Requests | `requests`, `urllib3` | High; network execution, retry/session/TLS/timeout policy, and dependency-security ownership |
| HTML ops | `bs4` | Moderate; parser-version and in-place DOM mutation semantics |

Inventory flags for source lines are static indicators, not proof that a path
executed. The Requests inventory’s organization/local-path indicators occur at
the literal HTTP adapter mount strings and require manual interpretation; the
network classification is independently supported by the imports and calls.

No helper runtime validation, ML-helper migration, network request, filesystem
workflow, or import probe was performed.

## 12. Proposed dispositions and migration guidance

| Point | Proposed disposition | Required guidance before any later action |
| --- | --- | --- |
| NumPy | migrate | Array shape/dtype/error semantics, all three keys, package re-export, NumPy support matrix |
| Pandas CSV | retire-review | File selection/output/overwrite semantics, obsolete path removal, replacement for organization automation |
| Pandas Excel | migrate | Excel engine and sheet errors, categories/tags coercion and ordering, registry transition |
| Pillow watermark | migrate | Font/logo/image-mode/output/error semantics, destructive consumer separation, obsolete-path transition |
| Pillow ratio | retire-review | Aspect presets, dimensions, formats, quality, overwrite and directory behavior, both registry keys |
| Requests | retire-review | Retry/timeouts/TLS/proxy/headers/errors/session lifecycle, dependency security, package and registry transition |
| HTML ops | migrate | BeautifulSoup/parser support, in-place mutation semantics, three internal wrappers, all three registry keys |

These are recommendations only. They do not create an extraction repository or
package and do not approve a packaging change.

## 13. Non-executing shim feasibility

No shim is added here. A future owner-approved Phase 2B design could use a
non-executing tombstone module to preserve import resolution and provide a clear
migration error without importing optional dependencies. That would preserve
less behavior than a forwarding shim and therefore needs explicit compatibility
design.

Functional forwarding would import or execute the replacement and is not part
of this review. It is especially owner-sensitive for Requests network behavior,
Pillow/Pandas filesystem behavior, and the BeautifulSoup object model. Registry
targets remain unchanged.

## 14. Owner recommendations

| Point | Owner recommendation |
| --- | --- |
| NumPy | owner needed before migration |
| Pandas CSV | explicit unowned retirement risk may be accepted |
| Pandas Excel | owner needed before migration |
| Pillow watermark | owner needed before migration |
| Pillow ratio | explicit unowned retirement risk may be accepted |
| Requests | owner needed before shim support |
| HTML ops | owner needed before migration |

No responsible owner was approved by this review. Every machine-readable
`owner` field remains exactly `unassigned`. These recommendations are not owner
assignments. Issue #62 remains the owner-approval authority.

## 15. Torch 2.9.0 freeze

The active declarations remain unchanged:

- `configs/requirements/ml.txt`: `torch==2.9.0`
- `pyproject.toml`: `torch>=2.9.0`

Existing contract coverage rejects any other exact Torch pin. Torch 2.13 remains
deferred. No ML-helper runtime validation or migration was attempted.

## 16. Compatibility-window status and Phase 2B blockers

The notice start event is the Phase 2A merge at
`2026-07-23T00:40:54Z`. The 90-day threshold is
`2026-10-21T00:40:54Z`.

The public-beta deprecation cycle starts with this review and notice. It is
**not complete**. The threshold is not a Phase 2B authorization date: the later
of 90 elapsed days and one completed documented public-beta cycle controls, and
issue #62 owner approval is still required afterward.

Phase 2B remains blocked by:

1. the incomplete public-beta deprecation cycle;
2. the unelapsed 90-day minimum until the stated threshold;
3. all seven owners remaining unassigned;
4. unresolved migration, dependency, platform, security, and shim decisions;
5. current package re-exports and helper-internal consumers;
6. consumer feedback received during the notice window; and
7. separate owner approval under issue #62.

All 154 helper modules remain temporarily wheel-included. Helper source, package
discovery, registry targets, dependency declarations, Torch versions, and
runtime behavior remain unchanged. Phase 2B was not started.
