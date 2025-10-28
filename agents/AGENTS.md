# Agent Integration Guidelines

Automation interacting with modules under `agents/` or generating new toolkit
components must follow these guardrails:

- Prefer `python scripts/scaffold_module.py` for creating extensions or health
  providers. The scaffolder wires instrumentation, health registry registration,
  and TODO markers that downstream reviewers rely on. Never copy templates by
  hand when the helper can be used.
- Register health checks via `context.health_checks.register(...)` (for
  extensions) or `TelemetryManager.register_health_check(...)` (for out-of-band
  services). This ensures diagnostics and the Prometheus gauge
  `zscripts_health_checks_status` stay accurate.
- When writing CLI automation, import adapters from `agents.cli_adapter` rather
  than invoking subprocesses directly. The adapter propagates correlation IDs and
  telemetry toggles compatible with the observability stack.
- Respect TODO annotations with priority/effort tags. Leave existing tags intact
  unless the work is completed.

These rules apply to every file inside `agents/` and any scaffolded modules they
own.
