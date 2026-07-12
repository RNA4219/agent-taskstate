-- agent-taskstate 1.1.0 audited history migration.
BEGIN;
CREATE TABLE IF NOT EXISTS state_transitions (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '', actor_type TEXT NOT NULL, actor_id TEXT, run_id TEXT,
  changed_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(id)
);
CREATE TABLE IF NOT EXISTS context_bundle_sources (
  id TEXT PRIMARY KEY, context_bundle_id TEXT NOT NULL, typed_ref TEXT NOT NULL,
  source_kind TEXT NOT NULL, selected_raw INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(context_bundle_id) REFERENCES context_bundles(id)
);
ALTER TABLE context_bundles ADD COLUMN purpose TEXT NOT NULL DEFAULT 'continue_work';
ALTER TABLE context_bundles ADD COLUMN rebuild_level TEXT NOT NULL DEFAULT 'L1';
ALTER TABLE context_bundles ADD COLUMN summary TEXT;
ALTER TABLE context_bundles ADD COLUMN decision_digest_json TEXT;
ALTER TABLE context_bundles ADD COLUMN question_digest_json TEXT;
ALTER TABLE context_bundles ADD COLUMN diagnostics_json TEXT;
ALTER TABLE context_bundles ADD COLUMN raw_included INTEGER NOT NULL DEFAULT 0;
ALTER TABLE context_bundles ADD COLUMN generator_version TEXT NOT NULL DEFAULT 'legacy/1.0.1';
ALTER TABLE context_bundles ADD COLUMN generated_at TEXT;
UPDATE context_bundles SET generated_at = created_at;
UPDATE context_bundles SET diagnostics_json = '{"legacy_backfill":true}', rebuild_level = 'L1',
  generator_version = 'legacy/1.0.1' WHERE diagnostics_json IS NULL;
INSERT OR IGNORE INTO schema_version(version, name, applied_at)
VALUES (2, 'state-history-bundle-audit-1.1.0', CURRENT_TIMESTAMP);
COMMIT;
