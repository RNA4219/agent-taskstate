# agent-taskstate SQLite 仕様書（MVP）

## 1. 目的
本仕様書は、agent-taskstate MVP の永続化基盤として使用する SQLite データベースの論理・物理仕様を定義する。対象は **単一ユーザー / ローカル実行 / CLI first** の運用であり、Task / State / Decision / Open Question / Run / Context Bundle を安定して保持できることを目的とする。

---

## 2. 前提
- DB エンジンは **SQLite 3** を使用する
- 文字コードは UTF-8 を前提とする
- 日時は原則 **UTC ISO 8601 文字列** で保持する
- JSON は SQLite の `TEXT` として保持する
- ID は **ULID 形式の TEXT** を推奨する
- 単一プロセスまたは低競合前提とし、`task_state` の更新競合のみ optimistic lock で扱う

---

## 3. DB ファイル構成
MVP では 1 ファイル構成とする。

- 推奨ファイル名: `agent-taskstate.db`

将来的にバックアップやローテーションを考慮して、task 単位の JSON export を別途持つ。

---

## 4. PRAGMA 方針
初期化時に以下を設定する。

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA busy_timeout = 5000;
```

### 理由
- `foreign_keys = ON`: DB 内整合性を確保するため
- `WAL`: 読み書きの安定性と実用性能のため
- `NORMAL`: ローカル単体利用での妥当なバランス
- `MEMORY`: 一時領域コスト軽減
- `busy_timeout`: 短時間の競合待ち

---

## 5. 型・命名規約

### 5.1 基本型
- ID: `TEXT`
- 列挙値: `TEXT`
- JSON: `TEXT`
- 時刻: `TEXT`
- リビジョン: `INTEGER`
- 任意メタデータ: `TEXT`

### 5.2 テーブル命名
- 単数形ではなく **業務概念の単純名** を採用する
- 例: `task`, `task_state`, `decision`

### 5.3 カラム命名
- snake_case
- 外部参照は `*_id`
- typed_ref は `*_ref` または `*_refs_json`

---

## 6. テーブル一覧
MVP では以下の 6 テーブルを持つ。

1. `task`
2. `task_state`
3. `decision`
4. `open_question`
5. `run`
6. `context_bundle`

---

## 7. テーブル仕様

## 7.1 task
Task 本体。1 つの到達目標と 1 つの状態機械を表す。

### DDL
```sql
CREATE TABLE task (
  id TEXT PRIMARY KEY,
  parent_task_id TEXT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  goal TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  owner_type TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT NULL,
  FOREIGN KEY (parent_task_id) REFERENCES task(id)
);
```

### 制約
- `kind` は以下のいずれか
  - `bugfix`
  - `feature`
  - `research`
- `status` は以下のいずれか
  - `draft`
  - `ready`
  - `in_progress`
  - `blocked`
  - `review`
  - `done`
  - `archived`
- `priority` は以下のいずれか
  - `low`
  - `medium`
  - `high`
  - `critical`
- `owner_type` は以下のいずれか
  - `human`
  - `agent`
  - `system`

### 推奨インデックス
```sql
CREATE INDEX idx_task_parent_task_id ON task(parent_task_id);
CREATE INDEX idx_task_status ON task(status);
CREATE INDEX idx_task_kind ON task(kind);
CREATE INDEX idx_task_owner ON task(owner_type, owner_id);
CREATE INDEX idx_task_priority ON task(priority);
CREATE INDEX idx_task_updated_at ON task(updated_at);
```

### 7.1.1 Phase 2 orchestration metadata 拡張
`pulse-kestra` の Phase 2 回復導線に対応するため、`task` には以下の追加属性を持たせてよい。

- `idempotency_key`
- `note_id`
- `trace_id`
- `reply_target`
- `reply_state`
- `retry_count`
- `kestra_execution_id`
- `original_task_id`
- `trigger`
- `reply_text`
- `roadmap_request_json`

#### 運用ルール
- `retry_count` は `INTEGER NOT NULL DEFAULT 0` とする
- `reply_state` は `pending` / `sent` / `failed` / `skipped` を許容する
- `idempotency_key` と `trace_id` は replay / dedupe の検索キーとしてインデックス対象にする
- `reply_text` は notifier resend と notifier-only replay の正本として使う

---

## 7.2 task_state
Task の最新版の軽量ダッシュボード。会話履歴の代替。

### DDL
```sql
CREATE TABLE task_state (
  task_id TEXT PRIMARY KEY,
  revision INTEGER NOT NULL,
  current_step TEXT NOT NULL,
  constraints_json TEXT NOT NULL,
  done_when_json TEXT NOT NULL,
  current_summary TEXT NOT NULL,
  artifact_refs_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  confidence TEXT NOT NULL,
  context_policy_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES task(id)
);
```

### 制約
- `confidence` は以下のいずれか
  - `low`
  - `medium`
  - `high`
- `revision >= 1`
- JSON カラムは JSON 文字列を格納する
  - `constraints_json`: 配列
  - `done_when_json`: 配列
  - `artifact_refs_json`: 配列
  - `evidence_refs_json`: 配列
  - `context_policy_json`: オブジェクト

### 運用ルール
- 1 task に対して 1 行のみ保持する
- 更新時は `revision` をインクリメントする
- `state patch` では `expected_revision` が一致した場合のみ更新可能とする

### 推奨インデックス
```sql
CREATE INDEX idx_task_state_updated_at ON task_state(updated_at);
```

---

## 7.3 decision
意思決定ログ。

### DDL
```sql
CREATE TABLE decision (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  summary TEXT NOT NULL,
  rationale TEXT NULL,
  status TEXT NOT NULL,
  confidence TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  supersedes_decision_id TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT NULL,
  FOREIGN KEY (task_id) REFERENCES task(id),
  FOREIGN KEY (supersedes_decision_id) REFERENCES decision(id)
);
```

### 制約
- `status` は以下のいずれか
  - `proposed`
  - `accepted`
  - `rejected`
  - `superseded`
- `confidence` は以下のいずれか
  - `low`
  - `medium`
  - `high`
- `evidence_refs_json` は配列 JSON

### 運用ルール
- 削除は行わない
- 更新時は `status` 変更または `supersedes_decision_id` による履歴継承を使う

### 推奨インデックス
```sql
CREATE INDEX idx_decision_task_id ON decision(task_id);
CREATE INDEX idx_decision_status ON decision(status);
CREATE INDEX idx_decision_task_status ON decision(task_id, status);
CREATE INDEX idx_decision_updated_at ON decision(updated_at);
```

---

## 7.4 open_question
未解決論点。

### DDL
```sql
CREATE TABLE open_question (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  question TEXT NOT NULL,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  answer TEXT NULL,
  evidence_refs_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT NULL,
  FOREIGN KEY (task_id) REFERENCES task(id)
);
```

### 制約
- `priority` は以下のいずれか
  - `low`
  - `medium`
  - `high`
- `status` は以下のいずれか
  - `open`
  - `answered`
  - `deferred`
  - `invalid`
- `evidence_refs_json` は配列 JSON

### 運用ルール
- `answer` が存在する場合は通常 `status = answered` を推奨する
- `review` 遷移時には `priority = high` かつ `status = open` が 0 件であること

### 推奨インデックス
```sql
CREATE INDEX idx_open_question_task_id ON open_question(task_id);
CREATE INDEX idx_open_question_status ON open_question(status);
CREATE INDEX idx_open_question_priority ON open_question(priority);
CREATE INDEX idx_open_question_task_status_priority ON open_question(task_id, status, priority);
```

---

## 7.5 run
1 回の処理実行記録。

### DDL
```sql
CREATE TABLE run (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  run_type TEXT NOT NULL,
  status TEXT NOT NULL,
  input_ref TEXT NULL,
  output_ref TEXT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT NULL,
  metrics_json TEXT NULL,
  metadata_json TEXT NULL,
  FOREIGN KEY (task_id) REFERENCES task(id)
);
```

### 制約
- `actor_type` は以下のいずれか
  - `human`
  - `agent`
  - `system`
- `run_type` は以下のいずれか
  - `plan`
  - `execute`
  - `review`
  - `summarize`
  - `sync`
  - `manual`
- `status` は以下のいずれか
  - `running`
  - `succeeded`
  - `failed`
  - `cancelled`
- `metrics_json` はオブジェクト JSON を想定する

### 運用ルール
- `run start` で行を作成し `status = running`
- `run finish` で `status`, `ended_at`, `output_ref` を更新する
- 削除は行わない

### 推奨インデックス
```sql
CREATE INDEX idx_run_task_id ON run(task_id);
CREATE INDEX idx_run_status ON run(status);
CREATE INDEX idx_run_run_type ON run(run_type);
CREATE INDEX idx_run_started_at ON run(started_at);
CREATE INDEX idx_run_task_started_at ON run(task_id, started_at);
```

---

## 7.6 context_bundle
毎回の処理入力束。

### DDL
```sql
CREATE TABLE context_bundle (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  build_reason TEXT NOT NULL,
  state_snapshot_json TEXT NOT NULL,
  included_decision_refs_json TEXT NOT NULL,
  included_open_question_refs_json TEXT NOT NULL,
  included_artifact_refs_json TEXT NOT NULL,
  included_evidence_refs_json TEXT NOT NULL,
  expected_output_schema_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT NULL,
  FOREIGN KEY (task_id) REFERENCES task(id)
);
```

### 制約
- `build_reason` は以下のいずれか
  - `normal`
  - `ambiguity`
  - `review`
  - `high_risk`
  - `recovery`
- `state_snapshot_json` はオブジェクト JSON
- `included_*_refs_json` は配列 JSON
- `expected_output_schema_json` はオブジェクト JSON

### 運用ルール
- Context Bundle は immutable とする
- 再生成時は新規行を追加する

### 推奨インデックス
```sql
CREATE INDEX idx_context_bundle_task_id ON context_bundle(task_id);
CREATE INDEX idx_context_bundle_created_at ON context_bundle(created_at);
CREATE INDEX idx_context_bundle_task_created_at ON context_bundle(task_id, created_at);
```

---

## 8. 整合性ルール

### 8.1 Task 状態遷移整合
状態遷移そのものはアプリケーション層で検証する。DB では列挙値のみを制約する。

### 8.2 Review 遷移条件
`review` へ遷移する前にアプリケーション層で以下を確認する。
- high priority の `open_question(status = open)` が 0 件
- `decision(status IN ('accepted','proposed'))` が 1 件以上

### 8.3 Done 遷移条件
`done` へ遷移する前にアプリケーション層で以下を確認する。
- `done_when_json` の全条件が満たされている
- `current_summary` が空でない
- 少なくとも 1 回 `review` 状態を通過済みである

### 8.4 Optimistic Lock
`task_state` 更新時の SQL 条件は以下のようにする。

```sql
UPDATE task_state
SET
  revision = revision + 1,
  current_step = :current_step,
  constraints_json = :constraints_json,
  done_when_json = :done_when_json,
  current_summary = :current_summary,
  artifact_refs_json = :artifact_refs_json,
  evidence_refs_json = :evidence_refs_json,
  confidence = :confidence,
  context_policy_json = :context_policy_json,
  updated_at = :updated_at
WHERE task_id = :task_id
  AND revision = :expected_revision;
```

更新件数 0 件の場合は `conflict` とする。

---

## 9. 参照仕様
agent-taskstate は DB 内では外部オブジェクトの実体を持たず、typed_ref を保持する。

### 形式
```text
<namespace>:<entity_type>:<id>
```

### 例
- `agent-taskstate:task:01H...`
- `agent-taskstate:decision:01H...`
- `memx:evidence:01H...`
- `memx:artifact:01H...`
- `tracker:jira:PROJ-123`

### 格納先
- `artifact_refs_json`
- `evidence_refs_json`
- `included_*_refs_json`
- `input_ref`
- `output_ref`

---

## 10. トランザクション方針

### 10.1 単一書き込み
以下の操作は 1 トランザクションで処理する。
- task create
- task set-status
- state put / patch
- decision add / accept / reject
- question add / answer / defer
- run start / finish
- context build

### 10.2 複合更新
以下はアプリケーション層で 1 トランザクションとする。
- task 作成 + 初期 task_state 作成
- context build + run start
- decision supersede 更新

---

## 11. マイグレーション方針

### 11.1 管理方法
- `schema_version` テーブルで単純管理する
- 1 migration = 1 version を採用する

### DDL
```sql
CREATE TABLE schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
```

### 11.2 初期バージョン
- MVP 初期版は `version = 1`

---

## 12. Export 仕様
Task 単位で以下をまとめて JSON export できること。
- `task`
- `task_state`
- `decision[]`
- `open_question[]`
- `run[]`
- `context_bundle[]`

### 目的
- バックアップ
- 移行
- 監査
- 再現

Import は MVP 非必須だが、Export JSON は将来 Import しやすい形を維持する。

---

## 13. エラーと DB レイヤの責務
DB レイヤでは SQLite の例外をそのまま露出せず、アプリケーション層で以下へ写像する。

- `not_found`
- `validation_error`
- `invalid_transition`
- `conflict`
- `dependency_blocked`

### 例
- FK 制約違反 -> `validation_error`
- 更新件数 0 件（revision 不一致） -> `conflict`
- 遷移ガード違反 -> `invalid_transition`

---

## 14. 性能前提
MVP の性能要件は以下を目安とする。
- task 作成: 体感 1 秒未満
- state 更新: 体感 1 秒未満
- context bundle 作成: 体感 1 秒未満（外部参照なし）
- task 単位 export: 数百 ms 〜 数秒程度

SQLite 単体で扱える規模を前提とし、まずはローカル 1 ユーザーの実用性を優先する。

---

## 15. 将来拡張ポイント（MVP 外）
- `task_dependency` テーブル追加
- `task_state_snapshot` テーブル追加
- `label` / `tag` 正規化
- `owner` を別テーブル化
- JSON1 関数を使った簡易検索拡張
- memx / tracker bridge との typed_ref 検証補助

---

## 16. 一言要約
本 SQLite 仕様は、agent-taskstate を **エージェント向けの stateful tool backend** として成立させるための最小永続化仕様である。チャット履歴ではなく、Task / State / Decision / Question / Run / Context Bundle を明示的に保存することで、長期タスクを再構成可能にする。

