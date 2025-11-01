# Schemas

JSON schema definitions and helpers for normalised log payloads live here.
`normalized_log.json` is consumed by `zscripts/schemas/normalized.py` and
validated in `tests/test_configuration.py`.

The package initializer (`schemas/__init__.py`) exists so tools can `import schemas`
when bundling CLI distributions.
