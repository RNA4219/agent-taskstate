# workx 要件定義（ペライチ / MVP）

## 1. 目的
workx は、長期タスクの進行状態をチャット履歴や KV キャッシュに依存せず、構造化データとして保持するためのローカル状態管理基盤である。人間または LLM が、毎回必要な文脈を再構成して次の一手を出せることを目的とする。

## 2. 位置づけ
- **workx**: 内部の作業状態の正本
- **memx**: 記憶・証拠・知識の外部基盤（現時点では連携 optional）
- **tracker-bridge**: Jira / BTS / GitHub Issues 等との外部同期層（現時点では連携 optional）

workx 自体は大規模な自律エージェント基盤ではなく、**状態付き CLI / API / MCP バックエンド**として成立すればよい。

## 3. スコープ
### 含む
- task の管理
- task の現在状態（task_state）の管理
- decision の管理
- open question の管理
- run の記録
- context bundle の生成・保存

### 含まない（MVP 非ゴール）
- 高度な自律オーケストレーション
- 複数エージェント協調の完成形
- 高度な全文検索 / RAG
- Jira 等との完全双方向同期
- 重い Web UI
- 分散構成 / 複雑な認可設計

## 4. コア概念
### 4.1 Task
1つの到達目標を持ち、1つの状態機械で進められる単位。

### 4.2 Task State
最新版の軽量ダッシュボード。会話履歴の代替として使う。

### 4.3 Decision
何を、なぜ、どの確度で決めたかを保持する。

### 4.4 Open Question
未解決論点を明示的に保持する。

### 4.5 Run
1回の plan / execute / review / summarize / manual 処理を記録する。

### 4.6 Context Bundle
その時点の task に対して必要な入力束。会話継続ではなく、状態再構成で進めるための中心オブジェクト。

## 5. Task 粒度ルール
Task は「1つの到達目標を持ち、1つの状態機械で進められる単位」とする。

### Subtask に切る条件
以下のいずれかを満たす場合は subtask 化を推奨する。
- 完了条件が 3 個を超える
- 担当主体が分かれる
- 成果物が複数種類に分かれる
- open question が 5 件を超える
- current_step を 1 本で表現しづらい

### 外部 issue との関係
- 基本: **Jira issue 1 件 = workx task 1 件**
- ただし大きすぎる場合は **1:N** を許可する

## 6. Task 種別
MVP では以下の 3 種別のみを持つ。
- `bugfix`
- `feature`
- `research`

## 7. Status と状態遷移
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

例外遷移は**理由メモ必須**とする。

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

## 8. 必須属性
### 8.1 Task
- `id`
- `parent_task_id`
- `kind`
- `title`
- `goal`
- `status`
- `priority`
- `owner_type`
- `owner_id`
- `created_at`
- `updated_at`

### 8.2 Task State
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

### 8.3 Decision
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

### 8.4 Open Question
- `id`
- `task_id`
- `question`
- `priority` (`low` / `medium` / `high`)
- `status` (`open` / `answered` / `deferred` / `invalid`)
- `answer`
- `evidence_refs`
- `created_at`
- `updated_at`

### 8.5 Run
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

### 8.6 Context Bundle
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

## 9. task_state の責務境界
### 入れてよいもの
- current_step
- constraints
- done_when
- current_summary
- artifact_refs
- evidence_refs
- confidence
- context_policy

### 入れないもの
- 長文議論全文
- decision 本文
- open question 本文
- 実行ログ全文
- チャット履歴

task_state は **1 task につき最新版 1 件** を基本とする。

## 10. Context Bundle 生成契約
### 常に含めるもの
- task 基本情報
- 最新 task_state
- accepted decisions
- open な open_questions
- done_when
- current_step

### 条件付きで含めるもの
- proposed decisions
- artifact_refs
- evidence_refs

### evidence を含める条件
以下のいずれかに該当する場合は evidence を含める。
- task_state.confidence = low
- decision.confidence = low
- build_reason = review
- high priority の open question がある
- current_step が investigation または verification
- context_policy.force_evidence = true

### expected_output_schema（MVP）
```json
{
  "summary": "string",
  "proposed_actions": ["string"],
  "decision_candidates": ["string"],
  "question_candidates": ["string"],
  "evidence_needed": ["string"]
}
```

## 11. typed_ref 仕様
形式は以下で固定する。

```text
<namespace>:<entity_type>:<id>
```

### 例
- `workx:task:01H...`
- `workx:decision:01H...`
- `memx:evidence:01H...`
- `memx:artifact:01H...`
- `tracker:jira:PROJ-123`

**DB 横断 FK は持たない。**

## 12. 更新競合ルール
MVP では **optimistic lock** を採用する。
- task_state に `revision` を持つ
- update / patch 時に `expected_revision` を要求する
- 不一致時は `conflict` を返す
- 自動 merge は行わない

## 13. 削除・保管ルール
- task は物理削除せず `archived` にする
- decision は削除せず `superseded` / `rejected` を使う
- open_question は `invalid` / `answered` / `deferred` を使う
- run / context_bundle は削除しない

## 14. 出力契約
CLI / API / MCP の返却形式は以下で統一する。

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

### error.code
- `not_found`
- `validation_error`
- `invalid_transition`
- `conflict`
- `dependency_blocked`

## 15. 最小インターフェース
### task
- create
- show
- list
- update
- set-status

### state
- get
- put
- patch

### decision
- add
- list
- accept
- reject

### question
- add
- list
- answer
- defer

### run
- start
- finish

### context
- build
- show

## 16. 非機能要件（MVP）
- SQLite 単体で動作すること
- オフラインで使えること
- 単一ユーザー前提であること
- 主要操作が体感 1 秒未満であること
- task 単位の JSON export ができること
- CLI first、API / MCP は後付け可能であること

## 17. MVP 完了条件
以下をすべて満たした時点で MVP 完了とみなす。
- task を作成できる
- task_state を作成・更新できる
- decision を追加できる
- open question を追加・解決できる
- run を記録できる
- context bundle を生成できる
- 生成した context bundle を見て、人間または LLM が次の一手を出せる

