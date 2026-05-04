# Priority 5: pulse-kestra Phase 2 回復導線を支える task 拡張

## 目的

`pulse-kestra` の Phase 2 で必要になる durable dedupe、未通知再送、heartbeat 回復、manual replay を、`agent-taskstate` を正本にして運用可能にする。

## 現状の課題

MVP の `agent-taskstate` は task / state / run / bundle の最小管理には十分だが、オーケストレータ連携で必要な以下が不足している。

- durable dedupe 用の task 検索キー
- reply 再送に必要な保存本文
- retry / replay の累積回数
- orchestration execution ID
- `trace_id` ベースの replay 解決
- heartbeat 向けの時刻条件検索

この不足により、`pulse-kestra` 側で Phase 2 の回復導線を設計しても、正本データが保存できず実運用で破綻する。

## 要求

### 1. task に orchestration metadata を追加する

最低限、以下を task に持たせる。

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

### 2. task list の探索能力を拡張する

最低限、以下の filter が必要。

- `--updated-before`
- `--idempotency-key`
- `--reply-state`
- `--trace-id`

### 3. task update --json を orchestration metadata に対応させる

reply 再送や replay 後処理で必要になるため、`reply_state` `retry_count` `reply_text` `kestra_execution_id` などを更新できなければならない。

### 4. replay と resend は task 正本だけで成立する

運用時に外部ログやメモリ断片へ依存しないよう、少なくとも以下は task から再構成できなければならない。

- dedupe 判定
- replay 元 task 解決
- 元 reply 本文
- retry 回数
- orchestration 実行 ID

## 受入条件

- `pulse-kestra` が task 正本だけで dedupe / resend / replay を実行できる
- `trace_id` 指定の replay が `agent-taskstate` 単体で解決できる
- `reply_text` を保存し、notifier-only replay で再利用できる
- heartbeat が `updated_before` と `reply_state` を使って回復対象を抽出できる

## 完了の定義

`agent-taskstate` が「MVP 状態管理ツール」から「外部オーケストレータの回復導線も支える state backend」に拡張されること。
