# Future Roadmap

Zscripts is a local, deterministic **repository review workspace**.

Authoritative direction:

- [Zscripts 0.2 Repository Review Workspace Roadmap](product/REPOSITORY_INTELLIGENCE_ROADMAP.md)
- [Umbrella issue #76](https://github.com/Nobodyworld/dev-logger-zscripts/issues/76)

## Product workflow

```text
Scan → Explore → Review → Compare → Handoff
```

The workspace is the product. Analysis remains local-first, read-only, deterministic,
reviewable, and usable without an LLM or cloud account. The maintained log-toolkit CLI remains
a supported capability; legacy helpers remain compatibility-only under #73.

## Current highest-impact sequence

1. #155 — align product identity, supported-use guidance, and current validation records.
2. #154 — resolve the focused control-contrast/focus question before broader stylesheet work.
3. #136 — consolidate current compatible dependency maintenance from then-current main.
4. #156 — reduce bounded Repository Review structural hotspots without changing behavior.
5. #94 — begin the first architecture-evidence vertical slice.

#54 continues in parallel as the security/release-closeout authority and is externally blocked
on a verified NLTK correction. That blocker does not freeze unrelated product work.

Phase 2B legacy-helper extraction/removal remains prohibited until #73's compatibility and
public-beta deprecation gates are satisfied.

## Deferred directions

Additional language analyzers, cloud/multi-user service, automatic refactoring, LLM-required
classification, and stable release claims remain deferred until the current local product
tranche demonstrates a clean, maintainable foundation.
