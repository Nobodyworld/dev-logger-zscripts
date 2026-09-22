# Security Policy

## Archived status

Zscripts is an **archived reference implementation**. No version, branch, tag, package, or
artifact is supported for production use, and there is no continuing security-remediation
commitment.

At archival, the repository's independent dependency audit still reported the known NLTK
condition historically tracked in issue #54. The repository was archived without suppressing,
ignoring, or dismissing that result.

| Version | Supported |
| --- | --- |
| `main` | No |
| Tagged pre-1.0 artifacts | No |

Anyone who forks or reuses this code assumes responsibility for dependency review, patching,
threat-model review, testing, and deployment security.

## Sensitive disclosures

Do not post credentials, private source, personal information, proprietary paths, exploit
details, or other sensitive vulnerability material in public issues or pull requests.

If a sensitive report concerns historical repository content, use GitHub private vulnerability
reporting when it is available for the archived repository. If that channel is unavailable,
use a verified private contact method published by the repository owner rather than disclosing
details publicly. No response-time or remediation commitment is provided.

## Historical security posture

Before archival, the repository used full-SHA GitHub Actions, least-privilege workflow
permissions, non-persisted checkout credentials, detect-secrets, Bandit, `pip-audit`,
Gitleaks in the local release profile, binary scanning, coverage gates, CodeQL, hostile-input
fixtures, read-only Repository Review contracts, localhost API restrictions, and packaging
smokes.

Those controls and their evidence remain useful historical implementation material. They do
not establish that the archived repository is currently secure or supported.

## Repository Review threat model

Repository Review treats analyzed repositories as hostile input. It uses bounded byte reads and
Python AST/static analysis rather than importing target modules or executing target project
commands. Read-only Git metadata queries use fixed no-shell operations; symlinks are excluded.
State is stored outside analyzed repositories. Source excerpts are explicit, bounded,
hash-verified, and not persisted, but may still expose sensitive source text locally.

The workspace binds to `127.0.0.1` and uses same-origin routes and restrictive browser
headers. Static analysis cannot prove runtime behavior, architectural intent, or code safety.

See [the Repository Review privacy contract](docs/repository-review.md#read-only-and-privacy-contract)
and [ARCHIVE.md](ARCHIVE.md).
