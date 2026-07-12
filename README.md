# agent-taskstate

Version: **1.1.0**

SQLite-backed task state CLI for durable task recovery. The canonical Python
package is `agent_taskstate`; `src.cli` remains a one-minor deprecation shim.

## 1.1.0 contract

- Python 3.10--3.13; console entry point: `agent-taskstate = agent_taskstate.cli:main`
- Existing plural tables are preserved and migrated transactionally.
- `tasks` status changes use `StateTransitionService` and append to `state_transitions`.
- `task history` returns chronological JSON; repeated status updates are no-ops.
- `state put` is insert-only; `state patch` is an atomic revision-guarded update.
- Context rebuild stores a complete immutable snapshot, audited source rows, raw flags,
  generator metadata, and resolver diagnostics.
- New refs are `<domain>:<entity_type>:<provider>:<entity_id>`; legacy 3-segment
  refs are read-compatible and canonicalized on write.
- Tracker outbound operations exist only as explicit `tracker comment` and
  `tracker status` commands. Secrets are represented by environment variable names.

## Verification

```powershell
uv run pytest -q
python -m build
agent-taskstate --help
```

仕様正本は `docs/src/`、DB正本は `docs/schema/agent-taskstate.sql`、
検収記録は `docs/acceptance/` です。
