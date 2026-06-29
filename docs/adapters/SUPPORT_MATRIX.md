# Adapter Support Matrix

This matrix is the canonical support contract for the core
cross-language log normalization and diagnostic CLI.

| Adapter | Identifier | Status | Example Log | Notes |
| --- | --- | --- | --- | --- |
| Python | `python` | Supported | `examples/python/sample.log` | Parses pytest, traceback, and packaging output. |
| JavaScript / TypeScript | `javascript` | Supported | `examples/javascript/sample.log` | Parses npm/yarn/pnpm style logs. |
| Java | `java` | Supported | `examples/java/sample.log` | Handles Maven/Gradle style diagnostics. |
| Go | `go` | Supported | `examples/go/sample.log` | Handles test/build output and module warnings. |
| Rust | `rust` | Supported | `examples/rust/sample.log` | Handles cargo build/test diagnostics. |
| .NET | `dotnet` | Supported | `examples/dotnet/sample.log` | Handles `dotnet test`/MSBuild style logs. |
| Docker | `docker` | Supported | `examples/docker/sample.log` | Handles image build and runtime diagnostics. |
| CI Pipelines | `ci` | Supported | `examples/ci/sample.log` | Handles CI orchestrator output including GitHub Actions. |

## Validation Source

The supported identifier set is enforced by automated tests in
`tests/test_adapters.py` and `tests/test_docs_contract.py`.
