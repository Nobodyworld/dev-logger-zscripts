# Adapters

The adapters package contains integration layers that translate toolchains into the
normalized logging interface used by the zscripts toolkit. Each language runtime or
platform has its own subpackage with adapter implementations and fixtures.

* `base.py` defines the shared Adapter protocol and helper classes.
* Language-specific subdirectories (for example `python/`, `go/`, `java/`) expose
  concrete adapters and fixtures.
* `registry.py` registers every adapter with the runtime so the CLI can resolve
  them by name at execution time.

See `docs/INDEX.md` for a full navigation map and `zscripts/infrastructure/adapters.py`
for the runtime registry that consumes these helpers.
