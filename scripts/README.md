# Automation Scripts

Utility scripts that support development, release automation, and quality
reporting live in this directory. They are safe to call from CI or local
environments and honour the configuration defaults documented in `README.md`.

Notable entries:

* `dev_start.py` bootstraps local development with telemetry disabled.
* `collect_quality_metrics.py` analyses code complexity, dependency health, and
  CLI responsiveness, emitting JSON metrics suitable for dashboards.
* `tag_release.py` bumps the project version in `pyproject.toml` and optionally
  creates a git tag.
* `scaffold_module.py` generates extension or health-check skeletons compliant
  with the guidance in `docs/guides/`.
