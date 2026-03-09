---
name: agent-taskstate-maintainer
description: Maintain and verify the C:\Users\ryo-n\Codex_dev\agent-taskstate repository. Use when working in this repo to review requirements, fix implementation gaps, align code with docs, tests, and schema, update README guidance, or prepare acceptance, commit, and push. Triggers include requests about typed_ref, context bundles, resolver, tracker bridge, kv-priority-roadmap, and repo-specific code review.
---

# Agent-taskstate Maintainer

## Overview

Use this skill only inside `agent-taskstate`. Treat `docs/kv-priority-roadmap/` as requirement supplements that must stay consistent with the implementation.

## Workflow

1. Read the relevant context in this order when needed:
   - `README.md`
   - `BLUEPRINT.md`
   - `GUARDRAILS.md`
   - matching file under `docs/src/`
   - matching file under `docs/kv-priority-roadmap/`
2. Map the request to the main modules before editing:
   - `typed_ref`: `src/typed_ref.py`, `tests/test_typed_ref.py`, `docs/contracts/typed-ref.md`
   - context bundle: `src/context_bundle.py`, `tests/test_context_bundle.py`, `docs/schema/agent-taskstate.sql`
   - resolver: `src/resolver.py`, `tests/test_context_rebuild_resolver.py`
   - tracker bridge: `src/tracker_bridge.py`, `tests/test_tracker_bridge.py`
   - state transition: `src/state_transition.py`, `tests/test_state_transition.py`
3. Update implementation, tests, and schema/docs together when the behavior changes.
4. Validate with `pytest -q` before finishing. Use narrower suites only while iterating.
5. Inspect `git status --short` before commit and exclude `__pycache__`, `workflow-cookbook/`, and unrelated local artifacts.

## Repo Invariants

- Keep `typed_ref` in 4-segment canonical form: `<domain>:<entity_type>:<provider>:<entity_id>`.
- Keep `agent-taskstate` as the source of truth for internal task state. Treat tracker data as auxiliary input.
- Preserve context bundle auditability: diagnostics, source refs, raw-inclusion flags, and generator metadata must remain traceable.
- When asked for review, report bugs, requirement gaps, and regression risks before summaries.
- When editing docs, keep `README.md` agent-oriented and `README.human.md` human-oriented.

## Acceptance Pass

- Re-check the relevant roadmap item under `docs/kv-priority-roadmap/`.
- Confirm the touched tests cover the changed behavior.
- If schema or migration contracts moved, update both `docs/schema/agent-taskstate.sql` and `docs/migrations/001_init.sql`.
- Commit in Japanese and push only after verification succeeds.
