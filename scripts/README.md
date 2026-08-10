# Scripts

Automation entry points that support development and CI workflows live here.
Contributor, hosted CI, and local release checks share one implementation.

## Key Tools

- `quality_gate.py` — canonical cross-platform operation registry and the
  `check`, `quality`, and `release` profiles. GitHub Actions retains separately
  named steps while delegating each operation here.
- `check_legacy_helper_boundary.py` — standard-library-only Phase 2A surface,
  compatibility-manifest, maintained-core import, wheel-membership, and
  review-time helper-immutability checks. It never imports helper source.
- `validate_commit_message.py` — deterministic, standard-library-only
  Conventional Commit validator used by the local `commit-msg` hook.
- `no_binaries.py` — guards against committing binary artefacts.
- `evaluate_repository_review.py` — generates deterministic public dogfood
  fixtures and records sanitized, bounded Repository Review measurements
  through the existing application service. Evaluation output and SQLite data
  directories are mandatory explicit paths and must remain outside every
  resolved analysis root. Evaluation output format `2` uses integrity-manifest
  format `1` for its before/after repository proof.

Example:

```powershell
python scripts/evaluate_repository_review.py generate `
  --root C:\tmp\repository-review-public
python scripts/evaluate_repository_review.py evaluate `
  --subject public-medium=C:\tmp\repository-review-public\public-medium `
  --output C:\tmp\repository-review-results\medium.json `
  --data-directory C:\tmp\repository-review-results\data `
  --integrity-max-files 50000 `
  --integrity-max-file-size-bytes 268435456 `
  --integrity-max-total-bytes 2147483648
```

## Repository Review integrity manifest

The integrity manifest is independent of analyzer `ScanLimits` and does not
change discovery, evidence, repository identity, snapshot identity, or stored
schemas. It resolves each entered subject through
`RepositoryDiscovery.resolve_scope()`, so a nested Git input is measured at
the same enclosing Git root that analysis uses.

Git mode runs a fixed, no-shell `git ls-files` contract for tracked files plus
untracked nonignored files. Tracked files remain included even when a later
ignore rule matches them. Git-ignored content, `.git`, the analyzer's default
environment/cache directories, and optional `--integrity-exclude` patterns are
excluded before file content is opened. Fixed Git exclude patterns prevent an
unignored `.venv`, `node_modules`, cache, coverage, `dist`, or `build` tree from
forcing recursive owner-local enumeration. A second fixed, directory-collapsed
Git query supplies aggregate exclusion counts without reading ignored files.

Non-Git mode performs a sorted `os.walk(..., followlinks=False)`, prunes the
same default directories and `.git` markers, and applies the discovery layer's
documented bounded `.gitignore` subset. Negated ignore rules are not interpreted
in this fallback mode. Regular files of every type, including binary files, are
hashed in 1 MiB streaming chunks without decoding. Directory and file symlinks
are never followed; the UTF-8 link-target text is hashed as a `symlink` entry.
Unsupported filesystem entry types are counted and excluded.

Format `1` sorts normalized POSIX repository-relative paths by UTF-8 bytes. Its
canonical entry sequence is path, NUL, entry type, NUL, decimal size, NUL,
SHA-256 content or link-target digest, NUL. Absolute paths, timestamps, inode
data, owners, durations, and database values are never included. Public JSON
contains only aggregate file/byte counts, limits, exclusion reasons/counts,
before/after digests, completion state, and equality; it never emits the
in-memory relative-path list.

Defaults are 50,000 candidate entries, 256 MiB per entry, 2 GiB total included
bytes, and 64 MiB of Git path-list output. All are explicit CLI options. A
breach produces a path-free incomplete reason and no digest; evaluation fails
closed before analysis (or after analysis for an after-manifest failure).
`persistence.repository_bytes_unchanged` remains as a compatibility field, but
under evaluation output format `2` it means that both complete format-`1`
manifests have equal digests, mode, included counts/bytes, and exclusion counts.

The evaluator records Python `tracemalloc` peaks, which do not represent full
process or native memory. It never emits source text or absolute subject paths.

If a script requires configuration, document it in `configs/README.md` and link
the relevant section from the top-level `README.md`.
