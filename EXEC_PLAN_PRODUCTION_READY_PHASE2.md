# Production Readiness Refresh - Phase 2

## Goal
Address high-impact robustness gaps in the CLI and filesystem tooling so dry runs surface actionable status codes, tree snapshots expose concise summaries, and log collection guarantees clean resource management.

## Tasks
1. **Dry-run exit signalling**
   - Extend the collect dry-run flow to detect metadata retrieval issues.
   - Bubble up a dedicated error to surface a non-zero exit code while keeping user-facing warnings.
   - Adjust CLI tests to cover the new exit behaviour.

2. **Tree snapshot summarisation**
   - Enhance `iter_filtered_tree_lines` to gather directory/file counters, byte totals, and truncation counts.
   - Append a human-readable summary block to the emitted tree.
   - Add unit and CLI assertions verifying the summary content.

3. **Log collection resource hygiene**
   - Replace manual file-handle tracking in `collect_app_logs` with an `ExitStack` to guarantee closure and flushing.
   - Cover the regression with a targeted test that simulates exceptions mid-run.

## Validation
- Run `pytest` to confirm updated and new tests pass.
