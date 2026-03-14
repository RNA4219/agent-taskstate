# agent-taskstate Phase 2 追加仕様書（pulse-kestra 連携）

## 1. 目的

本仕様書は、`pulse-kestra` Phase 2 で必要になる durable dedupe、未通知再送、heartbeat 回復、manual replay を `agent-taskstate` の正本データとして成立させるための追加仕様を定義する。

MVP の current state / state history / run / context bundle を壊さずに、外部オーケストレータ連携に必要な最小拡張を加えることを目的とする。

---

## 2. 適用範囲

本仕様は以下に適用する。

- `task` の永続化項目
- `task create/show/list/update`
- `run start/finish`
- `pulse-kestra` の webhook / mention / heartbeat / notifier resend / manual replay

本仕様は `agent-taskstate` を正本とし、`pulse-kestra` 側の一時的 workaround を許容しない。

---

## 3. 設計原則

### 3.1 task は orchestration metadata の正本を持つ

`pulse-kestra` が再送、再実行、二重起票抑止に必要とする値は、task に保存し、再取得できなければならない。

### 3.2 state history と run history は既存原則を維持する

- task の進行状態は `task.status` と `task_state` / state history で追う
- 実行単位の成否は `run` で追う
- Phase 2 拡張はこれを置き換えず、task に orchestration metadata を追加する

### 3.3 manual replay は task_id / trace_id の両方を受け入れる

運用導線では task ID を直接使えることに加え、外部ログから `trace_id` だけで対象 task を解決できなければならない。

### 3.4 未通知再送は元の返信本文を再利用できなければならない

再送で汎用 fallback 文言に置き換わるだけでは、Phase 2 の回復導線として不十分である。`reply_text` を task に保存し、notifier resend と notifier-only replay の正本とする。

---

## 4. 追加データ項目

`task` に以下のカラムを追加する。

| カラム | 型 | 必須 | 説明 |
|---|---|---|---|
| `idempotency_key` | `TEXT` | 任意 | durable dedupe 用キー。Misskey webhook では `misskey:{note_id}` を想定 |
| `note_id` | `TEXT` | 任意 | Misskey note ID |
| `trace_id` | `TEXT` | 任意 | bridge / Kestra / notifier を横断する追跡 ID |
| `reply_target` | `TEXT` | 任意 | 返信先 note ID または provider 固有 reply target |
| `reply_state` | `TEXT` | 任意 | `pending` / `sent` / `failed` / `skipped` |
| `retry_count` | `INTEGER` | 必須 | retry / replay の累積回数。既定値 0 |
| `kestra_execution_id` | `TEXT` | 任意 | 最後に紐づいた Kestra execution ID |
| `original_task_id` | `TEXT` | 任意 | replay 元 task ID |
| `trigger` | `TEXT` | 任意 | `mention` / `heartbeat` / `manual_replay` などの起票契機 |
| `reply_text` | `TEXT` | 任意 | Misskey へ返す本文の正本 |
| `roadmap_request_json` | `TEXT` | 任意 | replay 用の元 request JSON |

### 4.1 `reply_state` の列挙値

- `pending`
- `sent`
- `failed`
- `skipped`

### 4.2 インデックス

最低限、以下の検索を支えるインデックスを追加する。

- `idx_task_idempotency_key`
- `idx_task_trace_id`
- `idx_task_reply_state`
- `idx_task_updated_at`
- `idx_task_original_task_id`

---

## 5. CLI 追加契約

### 5.1 `task create --json`

`task create --json` は、MVP 項目に加えて本仕様の追加カラムを受け付けなければならない。

最低限、以下を保存できること。

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

### 5.2 `task update --json`

`task update --json` は、既存の更新対象に加えて本仕様の追加カラムを更新できなければならない。

少なくとも以下の更新を許可する。

- `reply_state`
- `retry_count`
- `kestra_execution_id`
- `reply_text`
- `roadmap_request_json`
- `trace_id`
- `idempotency_key`
- `reply_target`
- `original_task_id`
- `trigger`
- `note_id`

### 5.3 `task list` 追加 filter

`task list` は既存 filter に加えて以下を受け付ける。

- `--updated-before <iso8601>`
- `--idempotency-key <string>`
- `--reply-state <pending|sent|failed|skipped>`
- `--trace-id <string>`

### 5.4 `task show` / `task list --json`

JSON 出力には、追加カラムをすべて含めなければならない。

---

## 6. 運用契約

### 6.1 durable dedupe

- webhook 受信時は `idempotency_key` で既存 task を検索する
- 一致 task が `ready` / `in_progress` / `review` / `done` の場合は新規起票しない
- retryable failure をどう扱うかは呼び出し側で判断してよいが、判定材料は task に残っていなければならない

### 6.2 heartbeat

heartbeat は少なくとも以下を検索できなければならない。

- `reply_state in (pending, failed)`
- `updated_before` を用いた stuck task
- `trace_id` や `idempotency_key` を保持した retry 候補

### 6.3 manual replay

- `task_id` 指定時はその task を replay 元とする
- `trace_id` 指定時は `task list --trace-id` で候補を解決する
- 複数 task が見つかった場合は、既定で最新 `updated_at` を採用する

### 6.4 notifier resend

- `reply_text` があればそれを正本として再送する
- `reply_text` が無い場合のみ artifact または fallback 文言に降格する
- `reply_state` と `retry_count` は resend/replay の結果に応じて更新する

---

## 7. Migration 方針

既存 DB に対しては非破壊 migration を行う。

### 必須条件

- 既存 task 行を壊さない
- 追加カラムは `NULL` 許容または安全な既定値を持つ
- `retry_count` は `DEFAULT 0` とする
- 既存の `task show` / `task list` 利用者を壊さない

---

## 8. 受け入れ条件

以下をすべて満たした時点で、本仕様の実装完了とみなす。

1. migration 後も既存 DB をそのまま読める
2. `task create --json` で Phase 2 追加項目を保存できる
3. `task update --json` で `reply_state` `retry_count` `kestra_execution_id` `reply_text` を更新できる
4. `task list --idempotency-key` で durable dedupe 検索ができる
5. `task list --trace-id` で manual replay の対象解決ができる
6. `task list --updated-before` と `--reply-state` で heartbeat 用探索ができる
7. `task show` と `task list --json` で追加項目を取得できる

---

## 9. pulse-kestra 側の前提

`pulse-kestra` は本仕様を前提に、以下を行う。

- mention 起票時に `idempotency_key` `note_id` `trace_id` `reply_target` `trigger` `roadmap_request_json` を保存する
- worker 成功時に `reply_text` を保存する
- notifier success/failure に応じて `reply_state` を更新する
- retry / replay 時に `retry_count` を増やす
- Kestra execution 開始時に `kestra_execution_id` を保存する

このため、`agent-taskstate` 側で追加項目を正規の task 属性として扱う必要がある。
