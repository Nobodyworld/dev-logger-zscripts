# Residual worktree cleanup fallback

`python scripts/worktree_residual_cleanup.py` is a deliberately narrow fallback for a Windows worktree directory that remains **after** normal, non-force `git worktree remove <path>` has already unregistered the worktree.

It is not a general cleanup tool. Do not use it on a registered worktree, the primary checkout, a pre-existing workspace, shared caches, user data, or a directory whose ownership/content is uncertain. Root `AGENTS.md` remains authoritative.

## 1. Inventory only

Write the inventory **outside** the residual root:

```powershell
python scripts/worktree_residual_cleanup.py inventory C:\agent-owned\residual `
  --repo C:\repos\dev-logger-zscripts `
  --owned-parent C:\agent-owned `
  --protected-root C:\repos\dev-logger-zscripts `
  --protected-root C:\other\protected-worktree `
  --output C:\evidence\residual-inventory.json
```

Inventory performs no removal. It:

- requires the target to be a strict descendant of the declared owned parent;
- rejects target/protected-root overlap;
- records whether Git still lists the target as a worktree;
- enumerates entries without descending through symlinks/junctions/reparse points;
- hashes regular files as raw bytes with SHA-256, so CRLF and same-length content changes remain visible;
- hashes link/reparse targets without traversing them;
- records empty directories and unsupported filesystem entry types;
- uses extended-length Windows paths for filesystem operations;
- defaults to 200,000 entries and 1 GiB per file, with explicit CLI overrides.

A registered target, unknown content, unsupported entry type, secret/database/user data, unexplained environment content, or uncertain ownership means **retain it**. Directory names such as `.venv`, `reports`, and `artifacts` do not prove disposability.

## 2. Review and approve the exact manifest

Inventory emits these fields as unapproved:

```json
{
  "approval": {
    "approved": false,
    "created_by_current_slice": false,
    "inactive_confirmed": false,
    "note": ""
  },
  "preservation": {
    "ref": "",
    "head": ""
  }
}
```

Only after reviewing every entry and separately proving preservation/inactive use, update the manifest with:

- `approved: true`;
- `created_by_current_slice: true`;
- `inactive_confirmed: true`;
- a non-empty approval note;
- an existing Git ref in `preservation.ref`;
- the exact 40-character commit preserved by that ref in `preservation.head`.

Do not remove entries from the manifest to make an unknown file disappear from review. Apply compares the complete live inventory to the complete approved inventory and fails on any difference.

## 3. Apply only the reviewed manifest

```powershell
python scripts/worktree_residual_cleanup.py apply C:\evidence\residual-inventory.json
```

Before removing anything, apply rechecks:

1. root/owned-parent/protected-root containment;
2. explicit approval, current-slice ownership, and inactive-use attestations;
3. the preservation ref resolves to the exact approved commit;
4. Git no longer registers the target as a worktree;
5. the residual contains no `.git` metadata;
6. every live file, directory, and reparse point exactly matches the approved manifest.

Removal is entry-by-entry. The tool never calls recursive deletion, `git clean`, hard reset, stash, force worktree removal, or cache cleanup. Files and link/reparse points are removed before directories; every entry is revalidated immediately before its operation. A directory parent that becomes a reparse point is rejected rather than traversed.

For symlinks/junctions, the link itself is removed; the external target is not traversed or deleted.

## Failure and partial-removal rule

Any mismatch or OS removal failure stops immediately. The tool does not broaden scope or retry with force. If some already-approved entries were removed before a later failure, **retain the remaining root and create a new read-only inventory**. Do not reuse the old approved manifest for a second apply.

An already-absent approved root returns `already-absent`; an empty approved root can be removed normally.

## Validation contract

The focused fixture suite covers:

- inventory non-mutation and raw CRLF hashing;
- empty and already-absent roots;
- long paths;
- internal, external, and broken links without traversal;
- a native Windows junction fixture when available;
- protected-root overlap;
- registered-worktree rejection;
- same-size changed content;
- unknown files;
- `.git` metadata rejection;
- exact preservation-ref verification;
- partial removal/lock failure behavior.

This helper is operational tooling only. It does not authorize cleanup of any specific path, branch deletion, product changes, security remediation, dependency updates, releases, or repository-setting changes.
