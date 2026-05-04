# agent-taskstate MVP 仕様書（Agent-First CLI / API / MCP）

## 1. 概要
agent-taskstate は、長期タスクの進行状態を構造化して保持し、エージェントまたは人間が毎回必要な文脈を再構成して次の一手を出せるようにするための **agent-first な状態管理ツール** である。

本 MVP では、**SQLite ベースのローカル CLI** を中核に据え、将来的な API / MCP 露出が容易な設計を採用する。目的は「大規模な自律エージェント基盤」を作ることではなく、**長い仕事を壊さず回すための状態付きツール群**を成立させることにある。

---

## 2. 設計原則

### 2.1 Agent-First
- 人間向け UX よりも、**機械が叩きやすい安定した入出力**を優先する
- すべての操作は **明示的・決定的・JSON 互換** であることを目指す
- エージェントは agent-taskstate を「考える存在」ではなく、**状態を読むための作業台**として使う

### 2.2 Chat-History-Free
- チャット履歴を正本にしない
- `task_state` と `context_bundle` により、会話継続ではなく **状態再構成** で進める

### 2.3 Append-Oriented
- `decision`, `open_question`, `run`, `context_bundle` は履歴を残す
- 変更は上書きよりも「追加と状態更新」を優先する

### 2.4 Loose Coupling
- memx や tracker とは typed_ref による疎結合連携を行う
- DB 横断 FK は持たない

---

## 3. MVP スコープ

### 3.1 含む
- Task の作成・更新・状態遷移
- Task State の取得・更新
- Decision の追加・状態更新
- Open Question の追加・状態更新
- Run の開始・終了
- Context Bundle の生成・参照
- Task 単位の JSON export

### 3.2 含まない
- 自律実行ランタイム
- 複数エージェント協調制御
- Jira / GitHub Issues との完全同期
- 高度な検索 / 埋め込み検索
- GUI / Web UI
- 認可・権限管理
- 分散構成

---

## 4. システムコンテキスト

```text
LLM / Human
   ↓
agent-taskstate CLI / API / MCP
   ↓
agent-taskstate core logic
   ↓
SQLite
```

将来拡張:

```text
agent-taskstate --typed_ref--> memx
agent-taskstate --typed_ref--> tracker-bridge
```

agent-taskstate 自身は、知識本体や外部 issue 本体を保持しない。保持するのは **内部作業状態** である。

---

## 5. ドメインモデル

### 5.1 Task
1つの到達目標を持ち、1つの状態機械で進められる単位。

#### 必須属性
- `id`
- `parent_task_id`
- `kind` (`bugfix` / `feature` / `research`)
- `title`
- `goal`
- `status`
- `priority`
- `owner_type` (`human` / `agent` / `system`)
- `owner_id`
- `created_at`
- `updated_at`

### 5.2 Task State
最新版の軽量ダッシュボード。

#### 必須属性
- `task_id`
- `revision`
- `current_step`
- `constraints`
- `done_when`
- `current_summary`
- `artifact_refs`
- `evidence_refs`
- `confidence`
- `context_policy`
- `updated_at`

#### 責務
- 現在の作業地点を示す
- 会話履歴の代替となる
- 長文議論や判断本文は持たない

### 5.3 Decision
何を、なぜ、どの確度で決めたか。

#### 必須属性
- `id`
- `task_id`
- `summary`
- `rationale`
- `status` (`proposed` / `accepted` / `rejected` / `superseded`)
- `confidence`
- `evidence_refs`
- `supersedes_decision_id`
- `created_at`
- `updated_at`

### 5.4 Open Question
未解決論点。

#### 必須属性
- `id`
- `task_id`
- `question`
- `priority` (`low` / `medium` / `high`)
- `status` (`open` / `answered` / `deferred` / `invalid`)
- `answer`
- `evidence_refs`
- `created_at`
- `updated_at`

### 5.5 Run
1回の処理実行単位。

#### 必須属性
- `id`
- `task_id`
- `actor_type`
- `actor_id`
- `run_type` (`plan` / `execute` / `review` / `summarize` / `sync` / `manual`)
- `status`
- `input_ref`
- `output_ref`
- `started_at`
- `ended_at`

### 5.6 Context Bundle
その時点の task に必要な入力束。

#### 必須属性
- `id`
- `task_id`
- `build_reason` (`normal` / `ambiguity` / `review` / `high_risk` / `recovery`)
- `state_snapshot`
- `included_decision_refs`
- `included_open_question_refs`
- `included_artifact_refs`
- `included_evidence_refs`
- `expected_output_schema`
- `created_at`

---

## 6. Task 粒度ルール
Task は「1つの到達目標を持ち、1つの状態機械で進められる単位」とする。

### Subtask に切る条件
以下のいずれかを満たす場合は subtask 化を推奨する。
- 完了条件が 3 個を超える
- 担当主体が分かれる
- 成果物が複数種類に分かれる
- open question が 5 件を超える
- current_step を 1 本で表現しづらい

### 外部 issue との関係
- 基本: **Jira issue 1 件 = agent-taskstate task 1 件**
- ただし大きすぎる場合は **1:N** を許可する

---

## 7. 状態遷移仕様

### 7.1 Status
- `draft`
- `ready`
- `in_progress`
- `blocked`
- `review`
- `done`
- `archived`

### 7.2 許可遷移
- `draft -> ready`
- `ready -> in_progress`
- `in_progress -> blocked`
- `blocked -> in_progress`
- `in_progress -> review`
- `review -> in_progress`
- `review -> done`
- `done -> archived`

### 7.3 例外遷移
- `draft -> archived`
- `done -> in_progress`

例外遷移は理由メモ必須とする。

### 7.4 遷移ガード
#### `ready`
- goal が空でない
- done_when が 1 件以上ある
- kind が設定済み

#### `in_progress`
- task_state が存在する
- current_step が空でない

#### `review`
- high priority の open question が 0 件
- accepted または proposed の decision が 1 件以上ある

#### `done`
- done_when がすべて満たされている
- current_summary がある
- review を 1 回以上通過している

---

## 8. Context Bundle 仕様

### 8.1 常に含めるもの
- task 基本情報
- 最新 task_state
- accepted decisions
- open な open_questions
- done_when
- current_step

### 8.2 条件付きで含めるもの
- proposed decisions
- artifact_refs
- evidence_refs

### 8.3 evidence を含める条件
以下のいずれかに該当する場合は evidence を含める。
- `task_state.confidence = low`
- `decision.confidence = low`
- `build_reason = review`
- high priority の open question がある
- `current_step` が `investigation` または `verification`
- `context_policy.force_evidence = true`

### 8.4 expected_output_schema（MVP）
```json
{
  "summary": "string",
  "proposed_actions": ["string"],
  "decision_candidates": ["string"],
  "question_candidates": ["string"],
  "evidence_needed": ["string"]
}
```

---

## 9. typed_ref 仕様
形式:

```text
<namespace>:<entity_type>:<id>
```

例:
- `agent-taskstate:task:01H...`
- `agent-taskstate:decision:01H...`
- `memx:evidence:01H...`
- `memx:artifact:01H...`
- `tracker:jira:PROJ-123`

制約:
- DB 横断 FK は持たない
- 返却値や内部参照でも typed_ref を利用可能とする

---

## 10. CLI 仕様（MVP）

### 10.1 設計方針
- すべてのコマンドは **JSON 出力可能** とする
- 標準出力は機械可読を優先する
- 引数は短縮よりも明示性を優先する

### 10.2 コマンド一覧

#### task
- `agent-taskstate task create`
- `agent-taskstate task show --task <id>`
- `agent-taskstate task list [--status ...] [--kind ...] [--owner-type ...] [--owner-id ...]`
- `agent-taskstate task update --task <id> ...`
- `agent-taskstate task set-status --task <id> --to <status> [--reason ...]`

#### state
- `agent-taskstate state get --task <id>`
- `agent-taskstate state put --task <id> --file <json>`
- `agent-taskstate state patch --task <id> --file <json> --expected-revision <n>`

#### decision
- `agent-taskstate decision add --task <id> --file <json>`
- `agent-taskstate decision list --task <id> [--status ...]`
- `agent-taskstate decision accept --decision <id>`
- `agent-taskstate decision reject --decision <id>`

#### question
- `agent-taskstate question add --task <id> --file <json>`
- `agent-taskstate question list --task <id> [--status ...] [--priority ...]`
- `agent-taskstate question answer --question <id> --answer <text>`
- `agent-taskstate question defer --question <id> [--reason <text>]`

#### run
- `agent-taskstate run start --task <id> --run-type <type> --actor-type <type> [--actor-id <id>] [--input-ref <ref>]`
- `agent-taskstate run finish --run <id> --status <status> [--output-ref <ref>]`

#### context
- `agent-taskstate context build --task <id> --reason <reason>`
- `agent-taskstate context show --bundle <id>`

#### export
- `agent-taskstate export task --task <id> --output <file>`

### 10.3 CLI 出力形式
正常時:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

エラー時:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "conflict",
    "message": "revision mismatch"
  }
}
```

### 10.4 error.code
- `not_found`
- `validation_error`
- `invalid_transition`
- `conflict`
- `dependency_blocked`

---

## 11. API / MCP 適用方針
MVP は CLI first とするが、コマンド体系はそのまま API / MCP に写像できるようにする。

### 11.1 API への写像例
- `task create` -> `POST /tasks`
- `task show` -> `GET /tasks/{id}`
- `state patch` -> `PATCH /tasks/{id}/state`
- `context build` -> `POST /tasks/{id}/context-bundles`

### 11.2 MCP への写像例
- `agent_taskstate_task_create`
- `agent_taskstate_state_patch`
- `agent_taskstate_decision_add`
- `agent_taskstate_context_build`

MCP では、LLM が安全に叩けるよう **必須引数・型・エラーコード** を明示する。

---

## 12. 更新競合仕様
- `task_state` は `revision` による optimistic lock を採用する
- `state patch` は `expected_revision` を必須にする
- 不一致時は `conflict` を返す
- 自動 merge は行わない

`decision`, `open_question`, `run`, `context_bundle` は append-oriented に扱うため、競合を最小化する。

---

## 13. 削除・保管仕様
- task は物理削除せず `archived` とする
- decision は削除せず `superseded` / `rejected` を使う
- open question は `answered` / `deferred` / `invalid` を使う
- run / context_bundle は削除しない

---

## 14. Export 仕様
### 14.1 対象
Task 単位で以下をまとめて JSON export できること。
- task
- task_state
- decisions
- open_questions
- runs
- context_bundles

### 14.2 目的
- バックアップ
- 他環境移行
- 監査 / 再現

Import は MVP では非必須とするが、将来追加しやすい JSON 形式を採用する。

---

## 15. 非機能要件
- SQLite 単体で動作すること
- オフラインで利用可能であること
- 単一ユーザー前提であること
- 主要操作は体感 1 秒未満を目安とすること
- データは JSON export 可能であること
- ローカルファーストであること

---

## 16. 受け入れ条件
以下をすべて満たした時点で MVP 完了とみなす。
- task を作成できる
- task_state を作成・更新できる
- decision を追加し、accept / reject できる
- open question を追加し、answer / defer できる
- run を開始・終了できる
- context bundle を生成・参照できる
- 生成した context bundle を見て、人間または LLM が次の一手を出せる
- task 単位の JSON export ができる

---

## 17. MVP の一言要約
agent-taskstate MVP は、**エージェントが長期タスクを壊さず扱うための stateful tool backend** である。会話を覚えさせるのではなく、Task / State / Decision / Question / ContextBundle を明示的に持たせることで、長い仕事を再構成可能にする。

