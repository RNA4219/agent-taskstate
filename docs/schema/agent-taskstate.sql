-- agent-taskstate 1.1.0 plural logical schema.
CREATE TABLE schema_version (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  parent_task_id TEXT,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  goal TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  owner_type TEXT NOT NULL,
  owner_id TEXT,
  tracker_issue_ref TEXT,
  idempotency_key TEXT,
  note_id TEXT,
  trace_id TEXT,
  reply_target TEXT,
  reply_state TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  kestra_execution_id TEXT,
  original_task_id TEXT,
  trigger TEXT,
  reply_text TEXT,
  roadmap_request_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(parent_task_id) REFERENCES tasks(id)
);

CREATE TABLE task_states (
  task_id TEXT PRIMARY KEY,
  revision INTEGER NOT NULL,
  current_step TEXT NOT NULL,
  constraints_json TEXT NOT NULL,
  done_when_json TEXT NOT NULL,
  current_summary TEXT,
  artifact_refs_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  confidence TEXT,
  context_policy_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE decisions (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  summary TEXT NOT NULL,
  rationale TEXT,
  status TEXT NOT NULL,
  confidence TEXT,
  evidence_refs_json TEXT NOT NULL,
  supersedes_decision_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE open_questions (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  question TEXT NOT NULL,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  answer TEXT,
  evidence_refs_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  run_type TEXT NOT NULL,
  status TEXT NOT NULL,
  input_ref TEXT,
  output_ref TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE context_bundles (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  build_reason TEXT NOT NULL,
  purpose TEXT NOT NULL,
  rebuild_level TEXT NOT NULL,
  summary TEXT,
  state_snapshot_json TEXT NOT NULL,
  included_decision_refs_json TEXT NOT NULL,
  included_open_question_refs_json TEXT NOT NULL,
  included_artifact_refs_json TEXT NOT NULL,
  included_evidence_refs_json TEXT NOT NULL,
  expected_output_schema_json TEXT NOT NULL,
  decision_digest_json TEXT,
  question_digest_json TEXT,
  diagnostics_json TEXT,
  raw_included INTEGER NOT NULL DEFAULT 0,
  generator_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT,
  FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE context_bundle_sources (
  id TEXT PRIMARY KEY,
  context_bundle_id TEXT NOT NULL,
  typed_ref TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  selected_raw INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(context_bundle_id) REFERENCES context_bundles(id)
);

CREATE TABLE state_transitions (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT NOT NULL,
  reason TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  run_id TEXT,
  changed_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE tracker_connection (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  name TEXT NOT NULL,
  config_json TEXT NOT NULL,
  secret_env_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE issue_cache (
  id TEXT PRIMARY KEY,
  connection_id TEXT NOT NULL,
  issue_ref TEXT NOT NULL UNIQUE,
  remote_key TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  assignee TEXT,
  description TEXT,
  labels_json TEXT,
  raw_json TEXT,
  fetched_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(connection_id) REFERENCES tracker_connection(id)
);
CREATE TABLE entity_link (
  id TEXT PRIMARY KEY,
  tracker_issue_ref TEXT NOT NULL,
  agent_taskstate_entity_ref TEXT NOT NULL,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE sync_event (
  id TEXT PRIMARY KEY,
  connection_id TEXT NOT NULL,
  direction TEXT NOT NULL,
  status TEXT NOT NULL,
  issue_ref TEXT,
  details_json TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(connection_id) REFERENCES tracker_connection(id)
);
