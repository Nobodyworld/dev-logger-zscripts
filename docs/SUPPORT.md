# Support

Zscripts is a structured log collection, normalization, redaction, diagnostics, and reporting toolkit for developers and automation systems.

## Community Channels

- **Discussions**: Use GitHub Discussions for questions, feature ideas, and community tips.
- **Issues**: Report bugs via the Bug Report template; include CLI command, configuration snippet, and logs.
- **Security**: Follow the [SECURITY policy](../SECURITY.md) for vulnerability disclosure.

## Service Levels

| Request Type        | Target Response | Notes |
|---------------------|-----------------|-------|
| Security incidents  | 48 hours        | Handled privately with coordinated disclosure |
| Critical regressions| 2 business days | Provide reproduction steps and affected version |
| Feature requests    | 5 business days | Prioritised based on roadmap alignment |

## Self-Service Resources

- [README](../README.md) – Overview, CLI usage, and configuration reference.
- [ARCHITECTURE](architecture/ARCHITECTURE.md) – Component responsibilities and extension points.
- [CONTRIBUTING](../CONTRIBUTING.md) – Setup instructions, testing, and review checklist.
- [REPORT](plans/REPORT.md) & [PLAN](plans/PLAN.md) – Current architecture findings and roadmap.
- [STATUS](plans/STATUS.md) – Operational cadence, release status, and maintenance windows.

## Escalation

If you require additional assistance, email `support@zscripts.dev` with context,
urgency, and contact details. Include:

1. CLI invocation (e.g., `python -m zscripts collect --types ...`).
2. Relevant log snippets with `event=` and `error_id=` markers.
3. `zscripts` version, Python version, and operating system.

For enterprise support agreements, include contract identifiers so the request
can be routed to the correct on-call rotation.
