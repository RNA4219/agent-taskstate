-- 1.0.1 plural base schema contract.
-- The executable runner creates the same tables with IF NOT EXISTS.
-- Existing installations are extended by 002_1_1_0.sql.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, parent_task_id TEXT, kind TEXT NOT NULL, title TEXT NOT NULL,
  goal TEXT NOT NULL, status TEXT NOT NULL, priority TEXT NOT NULL,
  owner_type TEXT NOT NULL, owner_id TEXT, idempotency_key TEXT, note_id TEXT,
  trace_id TEXT, reply_target TEXT, reply_state TEXT, retry_count INTEGER NOT NULL DEFAULT 0,
  kestra_execution_id TEXT, original_task_id TEXT, trigger TEXT, reply_text TEXT,
  roadmap_request_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_states (
  task_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, current_step TEXT NOT NULL,
  constraints_json TEXT NOT NULL, done_when_json TEXT NOT NULL, current_summary TEXT,
  artifact_refs_json TEXT NOT NULL, evidence_refs_json TEXT NOT NULL, confidence TEXT,
  context_policy_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, summary TEXT NOT NULL, rationale TEXT,
  status TEXT NOT NULL, confidence TEXT, evidence_refs_json TEXT NOT NULL,
  supersedes_decision_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS open_questions (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, question TEXT NOT NULL, priority TEXT NOT NULL,
  status TEXT NOT NULL, answer TEXT, evidence_refs_json TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, actor_type TEXT NOT NULL, actor_id TEXT,
  run_type TEXT NOT NULL, status TEXT NOT NULL, input_ref TEXT, output_ref TEXT,
  started_at TEXT NOT NULL, ended_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS context_bundles (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, build_reason TEXT NOT NULL,
  state_snapshot_json TEXT NOT NULL, included_decision_refs_json TEXT NOT NULL,
  included_open_question_refs_json TEXT NOT NULL, included_artifact_refs_json TEXT NOT NULL,
  included_evidence_refs_json TEXT NOT NULL, expected_output_schema_json TEXT NOT NULL,
  created_at TEXT NOT NULL, metadata_json TEXT
);
