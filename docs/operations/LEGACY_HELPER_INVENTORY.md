# Legacy Helper Inventory and Phase 2 Decision Record

Status: evidence record; no Phase 2 disposition is approved by this document.

## 1. Audited revision

This inventory audits commit `030c796701f12aa21ab8cebdbbd2db82a9f82dd7` on
`chore/legacy-helper-inventory`. At preflight, that commit was also exact `main`.
The push-triggered `CI` run `29951313028` and its `quality` job `89029415449`
both completed successfully.

The machine-readable record is
[`legacy_helper_inventory.json`](legacy_helper_inventory.json).

## 2. Inventory methodology

The authoritative set comes from tracked Git entries under `zscripts/helpers`,
filtered to `.py` files and normalized to repository-relative POSIX paths. The
requested command `git ls-files "zscripts/helpers/**/*.py"` returns 153 domain
files under Git's pathspec semantics. It omits the tracked root-level
`zscripts/helpers/registry.py`; the prefix enumeration reconciles that file and
therefore records the complete set of 154 modules exactly once.

`scripts/inventory_legacy_helpers.py` uses only the Python standard library. It
parses every module with `ast`, classifies imports, calls, literals, and top-level
statements, and performs deterministic tracked-file searches for tests,
documentation, and registry references. Physical source lines are counted with
`str.splitlines()`, including blank and comment lines. The output is sorted, uses
no timestamp, and emits no local absolute paths.

The analyzer fails on Git errors, duplicate paths, missing tracked files, syntax
errors, unreadable source, or an invalid wheel. Risk flags are static evidence:
they identify review obligations and do not assert that a code path was executed.

## 3. Safety restrictions

- Helper source was never imported or executed during inventory generation.
- No helper file was moved, removed, rewritten, or behaviorally changed.
- No network/API call, credential lookup, organization-storage access, shell
  command, or helper filesystem operation was permitted.
- Dynamic probing was omitted. Thirty-two modules passed the static eligibility
  filter, but zero were probed and there were zero dynamic import failures.
- Any future probe must exclude filesystem mutation, move/delete, subprocess,
  network/API, credential, organization-specific, and import-time executable
  findings and must run in the constrained environment defined by issue #68.
- Wheel inspection read ZIP member names only; it did not install or import helper
  modules.

## 4. Inventory totals

The complete inventory contains **154 modules** and **10,563 source lines**.

| Domain | Modules |
| --- | ---: |
| computer_vision | 5 |
| environment_config | 23 |
| flask | 1 |
| google_api | 5 |
| html_processing | 7 |
| image_to_pdf | 2 |
| json_utils | 9 |
| machine_learning | 6 |
| matplotlib | 2 |
| numpy | 2 |
| openai | 9 |
| openai_formats | 6 |
| openpyxl | 2 |
| pandas | 11 |
| pillow | 21 |
| pypdf | 3 |
| requests | 2 |
| root | 1 |
| scikit_learn | 1 |
| sqlalchemy | 1 |
| utilities | 6 |
| web_crawl | 22 |
| wordpress | 7 |

## 5. Risk model and counts

The levels are evidence-based and mutually exclusive:

- `low`: no classified runtime, dependency, path, or import-time risk.
- `moderate`: read-only filesystem/environment behavior, third-party dependency,
  top-level execution, or isolated import/path defect without a dangerous
  combination.
- `high`: filesystem mutation, move/delete, subprocess, network/API, credential,
  or organization-specific behavior.
- `critical-review`: dangerous behaviors combine, such as credentials plus a
  remote client, organization paths plus destructive operations, or dangerous
  behavior at import time.

| Risk | Modules |
| --- | ---: |
| low | 21 |
| moderate | 24 |
| high | 34 |
| critical-review | 75 |

## 6. Recommended dispositions

Recommendations are per-module review inputs, not approvals. Lack of tests alone
never produces `delete-candidate`; the inventory assigns no module to deletion.

| Disposition | Modules |
| --- | ---: |
| retain-supported | 0 |
| quarantine-from-wheel | 113 |
| migrate-separate-package | 18 |
| archive | 0 |
| delete-candidate | 0 |
| manual-review | 23 |

High and critical-review modules are recommended for quarantine from the core
wheel. Moderate third-party-dependent modules are candidates for a separately
owned package. Low-risk modules without sufficient support evidence remain manual
review items. No module has enough combined low-risk and direct-test evidence for
an automatic `retain-supported` recommendation.

## 7. Third-party dependency findings

Static imports contain **29 unique non-standard-library roots**:

`PIL`, `PyPDF2`, `bs4`, `cv2`, `dotenv`, `google`,
`google_auth_oauthlib`, `googleapiclient`, `graph_tool`, `img2pdf`, `nltk`,
`no_post_blog_api`, `numpy`, `openai`, `openpyxl`, `opentelemetry`, `pandas`,
`pkg_resources`, `prometheus_client`, `pygame`, `requests`, `sklearn`,
`stdlib_list`, `tiktoken`, `torch`, `torchtext`, `tqdm`, `urllib3`, and `yaml`.

These are import roots, not normalized distribution names. They exceed the
current public support evidence and include heavy ML, image/PDF, crawler,
telemetry, Google, and OpenAI surfaces. A supported optional package would first
need an owner-reviewed import-root-to-distribution map, compatible version policy,
platform/Python matrix, license review, and isolated installation tests. This
record does not update dependencies or Torch.

## 8. Broken and obsolete import paths

- **49 modules** import obsolete top-level `helpers...` paths. The five observed
  targets are `helpers.pillow.add_watermark`, `helpers.utilities.fs`,
  `helpers.utilities.io`, `helpers.utilities.paths`, and
  `helpers.utilities.text`.
- `zscripts/helpers/json_utils/steps_to_json.py` imports bare root module `steps`.
- `zscripts/helpers/machine_learning/predict.py` imports bare root module
  `model_work`.
- `zscripts/helpers/registry.py` resolves the repository-root
  `configs/registry.yaml`, which is not shipped alongside the module at that
  relative checkout location in an isolated wheel.

The inventory reports valid `zscripts.helpers...` imports and relative imports
separately. No import is repaired in this phase.

## 9. Import-time behavior

**85 modules** contain executable top-level statements outside imports, static
assignments, definitions, and a guarded `if __name__ == "__main__"` block.
Evidence includes calls/object construction, loops, and runtime assignments.
This is a major compatibility and safety blocker because importing a package may
execute setup, I/O, client construction, or script workflow before a caller opts
in.

## 10. Filesystem access and mutation

- 78 modules have static filesystem-read evidence.
- 70 modules have filesystem-write evidence.
- 15 modules have move/delete evidence.
- 76 unique modules have write and/or move/delete evidence.

The classifier distinguishes reads from writes and destructive moves/deletes.
Calls include `open`, `Path.read_*`, `Path.write_*`, directory creation,
`shutil.copy*`, `shutil.move`, `shutil.rmtree`, and the enumerated `os` mutation
functions. No helper filesystem call was executed.

## 11. Subprocess, network, credential, and organization findings

- Subprocess or shell: **0 modules**.
- Network or API: **22 modules**.
- Environment access: **16 modules**.
- Credential access: **18 modules**.
- Organization-specific assumptions: **70 modules**.

Network findings cover HTTP libraries, remote clients, Google APIs, OpenAI, SMTP,
and crawler entry points. Credential findings include environment variables,
dotenv loaders, credential-like files, and client credential arguments.
Organization findings include `ORGANIZATION_STORAGE_ROOT`,
`ORGANIZATION_STORAGE`, `org_path`, `Shared Documents`, and hardcoded local or
organization-storage paths. Counts overlap because one module may combine several
risk classes.

## 12. Wheel and package inclusion

The unchanged wheel built from the audited tree contains **154 of 154** tracked
helper Python modules; none are missing. This confirms that legacy helpers are in
the current core distribution even when their third-party extras are not installed.
The wheel result is evidence for quarantine/extraction; it is not a packaging
change.

## 13. Test, documentation, and registry linkage

- 1 module has a filename-corresponding test; filename correspondence alone is
  not claimed as behavioral coverage.
- 5 modules are imported by exact module path in a test or smoke file.
- 10 modules are imported indirectly through package re-exports.
- 49 additional modules have only broad domain-level test evidence. Broad tests
  are explicitly not treated as direct coverage.
- 24 modules have module/domain documentation evidence; 130 do not.
- 7 modules are targets in `configs/registry.yaml`.

The linkage fields preserve the exact repository-relative evidence per module.
These sparse and overlapping signals do not establish a support contract for the
collection as a whole.

## 14. Representative high-risk evidence

- `zscripts/helpers/openai/chat.py`: OpenAI/network use, credential environment
  lookup, filesystem reads/writes, an organization-specific assumption, and an
  import-time executable statement.
- `zscripts/helpers/google_api/blog_posts_fetcher.py`: Google remote clients,
  credential files/client arguments, filesystem reads/writes, and an
  organization/local-path assumption.
- `zscripts/helpers/environment_config/move_pdfs_to_text_subfolder.py`: directory
  creation, `shutil.move`, and `org_path` coupling.
- `zscripts/helpers/machine_learning/model_c.py`: Torch/TorchText dependencies,
  file reads, organization-path coupling, and 22 executable top-level statements.
- `zscripts/helpers/web_crawl/crawler.py`: network access, filesystem writes, and
  four executable top-level statements.
- `zscripts/helpers/utilities/paths.py`: dotenv loading, credential/environment
  access, organization-storage assumptions, and import-time initialization. Its
  obsolete import path is consumed broadly across the legacy collection.

These examples are representative; the JSON contains the complete module-level
evidence and line numbers.

## 15. Compatibility implications

Immediate removal from the wheel would break existing `zscripts.helpers...`
imports, registry targets, package re-exports, and automation that relies on
today's accidental inclusion. Conversely, declaring the collection supported in
place would make the core distribution responsible for 29 third-party import
roots, organization-coupled behavior, import-time execution, credential handling,
and weak test/documentation coverage.

A compatibility plan must therefore inventory consumers of the seven registry
targets and public import paths, define a deprecation window, preserve shims where
safe, and clearly separate import compatibility from behavioral support. Obsolete
bare `helpers...` imports cannot be treated as an isolated-wheel contract.

## 16. Recommended Phase 2 approach

The evidence supports the current **quarantine/extraction direction**, with staged
compatibility rather than immediate deletion:

1. Freeze helper additions and document the current surface as legacy and
   unsupported except for explicitly named compatibility points.
2. Define an owner-approved compatibility/deprecation matrix for registry targets,
   package re-exports, and known external consumers.
3. Quarantine high and critical-review modules from the core wheel in a dedicated
   Phase 2 packaging change, preserving narrow non-executing shims where the owner
   accepts the cost.
4. Evaluate the 18 `migrate-separate-package` candidates by coherent domain, with
   independent ownership, dependency metadata, security review, isolated-wheel
   tests, and import-safety gates. Extraction may be a new package or other owned
   distribution location; this record creates none.
5. Manually adjudicate the 23 low-evidence items. Archive or deletion requires
   consumer evidence and owner approval; lack of tests is not sufficient.

This report supports Phase 2 planning but does **not** state that Phase 2 is
approved.

## 17. Explicit blockers to a supported public optional package

- 113 modules are recommended for quarantine and 109 are high or critical-review.
- 85 modules have executable import-time statements.
- 76 modules can write, move, or delete files.
- 22 modules use network/API surfaces; 18 access credentials; 70 embed
  organization-specific assumptions.
- 49 modules retain obsolete `helpers...` imports, 2 use unresolved bare root
  imports, and 1 relies on a repository-root configuration file.
- Dependency ownership is undefined across 29 import roots, including heavy and
  platform-sensitive ML/image stacks.
- Direct evidence is sparse: only 5 exact test imports and 24 documented modules,
  with broad domain tests not proving individual behavior.
- There is no approved API surface, semantic-versioning policy, maintainer/owner
  assignment, deprecation window, isolated-wheel test matrix, credential policy,
  or network/filesystem sandbox contract for the collection.

## 18. Schema summary

The JSON top level records schema version, Git scope, requested glob, methodology,
safety restrictions, allowed risk/disposition enums, summary counts, and sorted
module records. The exact audited SHA is recorded above in this decision record.
Each module record includes normalized path/module and
domain, source lines, third-party/internal/relative/obsolete/root imports,
repository configuration references, top-level statements, all risk flags, main
guard, direct/importing/indirect/domain tests, documentation, registry exposure,
wheel inclusion, risk, disposition, rationale, probe eligibility/status, and
line-oriented evidence.

## 19. Reproducibility

Build the unchanged wheel, then run the analyzer twice with the same wheel path.
The two generated files are byte-identical. Omitting `--wheel` remains
deterministic but records wheel status as `not-checked`; it does not guess.

## 20. Remaining owner decision under #62

The owner must decide the accepted compatibility window and whether Phase 2 is
(a) core-wheel quarantine with selected shims, (b) extraction of selected domains
to a separately owned package plus shims, or (c) a narrower supported subset.
That decision must also name owners for the seven registry-exposed modules and
approve the dependency/security/support contract. This evidence record does not
make or approve that decision.
