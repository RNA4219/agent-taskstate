-- agent-taskstate logical schema (MVP)
-- purpose:
--   manage long-task state outside LLM conversation memory
-- design rules:
--   - no cross-repo foreign keys
--   - typed_ref for external linkage
--   - state history is source of truth
--   - current state may be materialized on task for fast reads

CREATE TABLE task (
    id                    TEXT PRIMARY KEY,
    title                 TEXT NOT NULL,
    objective             TEXT,
    scope                 TEXT,
    description           TEXT,
    status                TEXT NOT NULL,
    priority              INTEGER NOT NULL DEFAULT 3,
    owner_type            TEXT,
    owner_id              TEXT,
    parent_task_id        TEXT,
    tracker_issue_ref     TEXT,
    idempotency_key       TEXT,
    note_id               TEXT,
    trace_id              TEXT,
    reply_target          TEXT,
    reply_state           TEXT,
    retry_count           INTEGER NOT NULL DEFAULT 0,
    kestra_execution_id   TEXT,
    original_task_id      TEXT,
    trigger               TEXT,
    reply_text            TEXT,
    roadmap_request_json  TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    archived_at           TEXT,
    FOREIGN KEY (parent_task_id) REFERENCES task(id)
);

CREATE TABLE task_state (
    id                    TEXT PRIMARY KEY,
    task_id               TEXT NOT NULL,
    from_state            TEXT,
    to_state              TEXT NOT NULL,
    reason                TEXT NOT NULL,
    actor_type            TEXT NOT NULL,
    actor_id              TEXT,
    run_id                TEXT,
    changed_at            TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES task(id)
);

CREATE TABLE decision (
    id                    TEXT PRIMARY KEY,
    task_id               TEXT NOT NULL,
    title                 TEXT NOT NULL,
    summary               TEXT NOT NULL,
    rationale             TEXT,
    status                TEXT NOT NULL DEFAULT 'active',
    decided_by_type       TEXT,
    decided_by_id         TEXT,
    run_id                TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES task(id)
);

CREATE TABLE decision_ref (
    id                    TEXT PRIMARY KEY,
    decision_id           TEXT NOT NULL,
    ref_type              TEXT NOT NULL,
    typed_ref             TEXT NOT NULL,
    role                  TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    FOREIGN KEY (decision_id) REFERENCES decision(id)
);

CREATE TABLE open_question (
    id                    TEXT PRIMARY KEY,
    task_id               TEXT NOT NULL,
    question              TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'active',
    priority              INTEGER NOT NULL DEFAULT 3,
    resolution_note       TEXT,
    resolved_at           TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES task(id)
);

CREATE TABLE open_question_ref (
    id                    TEXT PRIMARY KEY,
    open_question_id      TEXT NOT NULL,
    typed_ref             TEXT NOT NULL,
    role                  TEXT NOT NULL DEFAULT 'related',
    created_at            TEXT NOT NULL,
    FOREIGN KEY (open_question_id) REFERENCES open_question(id)
);

CREATE TABLE context_bundle (
    id                    TEXT PRIMARY KEY,
    task_id               TEXT NOT NULL,
    purpose               TEXT NOT NULL,
    rebuild_level         TEXT NOT NULL,
    summary               TEXT,
    state_snapshot_json   TEXT NOT NULL,
    decision_digest_json  TEXT,
    question_digest_json  TEXT,
    diagnostics_json      TEXT,
    raw_included          INTEGER NOT NULL DEFAULT 0,
    generator_version     TEXT,
    generated_at          TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES task(id)
);

CREATE TABLE context_bundle_source (
    id                    TEXT PRIMARY KEY,
    context_bundle_id     TEXT NOT NULL,
    typed_ref             TEXT NOT NULL,
    source_kind           TEXT NOT NULL,
    selected_raw          INTEGER NOT NULL DEFAULT 0,
    metadata_json         TEXT,
    created_at            TEXT NOT NULL,
    FOREIGN KEY (context_bundle_id) REFERENCES context_bundle(id)
);

CREATE TABLE run (
    id                    TEXT PRIMARY KEY,
    task_id               TEXT,
    context_bundle_id     TEXT,
    run_type              TEXT NOT NULL,
    actor_type            TEXT NOT NULL,
    actor_id              TEXT,
    status                TEXT NOT NULL,
    input_summary         TEXT,
    output_summary        TEXT,
    error_message         TEXT,
    started_at            TEXT NOT NULL,
    finished_at           TEXT,
    created_at            TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES task(id),
    FOREIGN KEY (context_bundle_id) REFERENCES context_bundle(id)
);

CREATE TABLE task_link (
    id                    TEXT PRIMARY KEY,
    task_id               TEXT NOT NULL,
    typed_ref             TEXT NOT NULL,
    link_type             TEXT NOT NULL,
    role                  TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES task(id)
);

CREATE INDEX idx_task_status ON task(status);
CREATE INDEX idx_task_owner ON task(owner_type, owner_id);
CREATE INDEX idx_task_parent ON task(parent_task_id);
CREATE INDEX idx_task_tracker_issue_ref ON task(tracker_issue_ref);
CREATE INDEX idx_task_idempotency_key ON task(idempotency_key);
CREATE INDEX idx_task_trace_id ON task(trace_id);
CREATE INDEX idx_task_reply_state ON task(reply_state);
CREATE INDEX idx_task_updated_at ON task(updated_at);
CREATE INDEX idx_task_original_task_id ON task(original_task_id);

CREATE INDEX idx_task_state_task_changed ON task_state(task_id, changed_at DESC);
CREATE INDEX idx_task_state_task_to_state ON task_state(task_id, to_state);

CREATE INDEX idx_decision_task_created ON decision(task_id, created_at DESC);
CREATE INDEX idx_decision_status ON decision(status);
CREATE INDEX idx_decision_ref_decision ON decision_ref(decision_id);
CREATE INDEX idx_decision_ref_typed_ref ON decision_ref(typed_ref);

CREATE INDEX idx_open_question_task_status ON open_question(task_id, status);
CREATE INDEX idx_open_question_priority ON open_question(priority);
CREATE INDEX idx_open_question_ref_question ON open_question_ref(open_question_id);

CREATE INDEX idx_context_bundle_task_generated ON context_bundle(task_id, generated_at DESC);
CREATE INDEX idx_context_bundle_purpose ON context_bundle(purpose);
CREATE INDEX idx_context_bundle_source_bundle ON context_bundle_source(context_bundle_id);
CREATE INDEX idx_context_bundle_source_ref ON context_bundle_source(typed_ref);

CREATE INDEX idx_run_task_started ON run(task_id, started_at DESC);
CREATE INDEX idx_run_bundle ON run(context_bundle_id);
CREATE INDEX idx_run_status ON run(status);

CREATE INDEX idx_task_link_task_type ON task_link(task_id, link_type);
CREATE INDEX idx_task_link_ref ON task_link(typed_ref);
