---
intent_id: INT-001
owner: your-handle
status: active   # draft|active|deprecated
last_reviewed_at: 2026-03-07
next_review_due: 2026-04-07
---

# Checklists: agent-taskstate CLI MVP

agent-taskstate CLI MVP の開発・運用におけるチェックリスト集。

---

## Development

### Task 作成・設計

- [ ] Task 作成前に `goal` と `done_when` を明確化
- [ ] `kind` を適切に設定（`bugfix` / `feature` / `research`）
- [ ] `priority` を業務重要度に合わせて設定
- [ ] 親 Task がある場合は `parent_task_id` を設定
- [ ] Subtask 化条件を確認：
  - [ ] 完了条件が 3 個以下か
  - [ ] 担当主体が単一か
  - [ ] open question が 5 件以下か

### Task State 設計

- [ ] `current_step` が明確か
- [ ] `constraints` に技術的制約を列挙
- [ ] `done_when` に完了条件を具体的に記述
- [ ] `confidence` を誠実に評価（low/medium/high）

### 状態遷移確認

- [ ] `draft -> ready` の前提条件：
  - [ ] goal が空でない
  - [ ] done_when が 1 件以上ある
  - [ ] kind が設定済み
- [ ] `ready -> in_progress` の前提条件：
  - [ ] task_state が存在する
  - [ ] current_step が空でない
- [ ] `in_progress -> review` の前提条件：
  - [ ] high priority の open question が 0 件
  - [ ] accepted または proposed の decision が 1 件以上
- [ ] `review -> done` の前提条件：
  - [ ] done_when がすべて満たされている
  - [ ] current_summary がある
  - [ ] review を 1 回以上通過している

### Decision 記録

- [ ] `summary` が簡潔かつ明確
- [ ] `rationale` で判断根拠を説明
- [ ] `confidence` を評価
- [ ] `evidence_refs` に根拠資料をリンク
- [ ] 古い Decision を置き換える場合は `supersedes_decision_id` を設定

### Open Question 管理

- [ ] 未解決論点を隠さず明示
- [ ] `priority` を適切に設定（特に `high` は review 遷移をブロック）
- [ ] 解決したら速やかに `answer` で回答記録
- [ ] 延期する場合は `defer` で理由を明記

---

## Pull Request / Review

### PR 作成前

- [ ] 関連 Task ID を PR 本文に記載
- [ ] 変更内容を要約して説明
- [ ] 影響範囲を特定
- [ ] 破壊的変更の有無を確認

### PR 本文テンプレート

```markdown
## Intent
- Task ID: agent-taskstate:task:01H...

## Summary
- 変更内容の要約

## Changes
- 変更ファイル一覧
- 主要な変更点

## Test Plan
- [ ] 単体テスト
- [ ] 結合テスト
- [ ] 手動確認

## Checklist
- [ ] state revision が最新
- [ ] decision で合意済み
- [ ] open question が解決済み
```

### レビュー観点

- [ ] 設計意図が Decision に記録されているか
- [ ] 未解決の Open Question が残っていないか
- [ ] Context Bundle で次の一手が判断できるか
- [ ] typed_ref が正しい形式か

### マージ前確認

- [ ] CI が通っている
- [ ] レビュアー承認済み
- [ ] コンフリクト解消済み
- [ ] CHANGELOG 更新（該当する場合）

---

## Ops / Incident

### インシデント初動対応

- [ ] 影響範囲の特定
- [ ] 関連 Task の特定
- [ ] 状態を `blocked` に変更
- [ ] Open Question で問題を明確化

### 復旧作業

- [ ] 原因特定のための Decision 記録
- [ ] 修正方針の Decision 記録
- [ ] Run で作業記録
- [ ] 状態を `in_progress` に戻す

### 事後対応

- [ ] 再発防止策を Decision として記録
- [ ] 再発防止 Task を作成（必要に応じて）
- [ ] 状態を `review` -> `done` に遷移

---

## Daily

### 入力確認

- [ ] 新規 Task の有無
- [ ] blocked Task の有無
- [ ] 優先度の高い Task の確認

### 状態確認

- [ ] `in_progress` が滞留していないか
- [ ] `review` 待ちがないか
- [ ] high priority の Open Question がないか

### DB 整合性

- [ ] `schema_version` が最新
- [ ] 孤立した task_state がない
- [ ] revision 不整合がない

---

## Release

### 事前確認

- [ ] 全 Task の状態確認
- [ ] 未解決 Open Question の確認
- [ ] draft Task の保留理由確認

### Task 完了確認

- [ ] `done_when` 全項目が満たされている
- [ ] `current_summary` が記載されている
- [ ] review を通過している
- [ ] 関連 Run が成功している

### Export・バックアップ

- [ ] 完了 Task の JSON Export
- [ ] DB バックアップ作成
- [ ] Export ファイルの整合性確認

### リリース後

- [ ] 完了 Task を `archived` に変更
- [ ] CHANGELOG 更新
- [ ] 関連資料の更新

---

## Hygiene

### 定期メンテナンス

- [ ] 古い Task のアーカイブ確認
- [ ] `superseded` Decision の整理
- [ ] `deferred` Open Question の再評価

### データ品質

- [ ] typed_ref の有効性確認
- [ ] JSON フィールドの整合性
- [ ] タイムスタンプの妥当性

### ドキュメント同期

- [ ] MVP Spec との整合性
- [ ] SQLite Spec との整合性
- [ ] RUNBOOK の最新化

---

## Command Quick Reference

### Task

```bash
agent-taskstate task create --kind <bugfix|feature|research> --title TEXT --goal TEXT --priority <low|medium|high|critical> --owner-type <human|agent|system> --owner-id ID
agent-taskstate task show --task ID
agent-taskstate task list [--status STATUS] [--kind KIND]
agent-taskstate task update --task ID [--title TEXT] [--goal TEXT] ...
agent-taskstate task set-status --task ID --to STATUS [--reason TEXT]
```

### State

```bash
agent-taskstate state get --task ID
agent-taskstate state put --task ID --file JSON
agent-taskstate state patch --task ID --file JSON --expected-revision N
```

### Decision

```bash
agent-taskstate decision add --task ID --file JSON
agent-taskstate decision list --task ID [--status STATUS]
agent-taskstate decision accept --decision ID
agent-taskstate decision reject --decision ID
```

### Question

```bash
agent-taskstate question add --task ID --file JSON
agent-taskstate question list --task ID [--status STATUS] [--priority PRIORITY]
agent-taskstate question answer --question ID --answer TEXT
agent-taskstate question defer --question ID [--reason TEXT]
```

### Run

```bash
agent-taskstate run start --task ID --run-type <plan|execute|review|summarize|sync|manual> --actor-type <human|agent|system> --actor-id ID [--input-ref REF]
agent-taskstate run finish --run ID --status <succeeded|failed|cancelled> [--output-ref REF]
```

### Context

```bash
agent-taskstate context build --task ID --reason <normal|ambiguity|review|high_risk|recovery>
agent-taskstate context show --bundle ID
```

### Export

```bash
agent-taskstate export task --task ID --output FILE
```

---

## Status Flow Diagram

```
draft ─────────────────────────────────────────────┐
  │                                                 │
  ▼                                                 │
ready ─────────────────────────────────────────────┤
  │                                                 │
  ▼                                                 │
in_progress ◄──────────────────────────────────────┤
  │  ▲                                              │
  │  │                                              │
  ▼  │                                              │
blocked ──────────► in_progress                    │
  │                                                 │
  ▼                                                 │
review ◄───────────────────────────────────────────┤
  │  ▲                                              │
  │  └──────────────────────────────────────────────┘
  ▼
done ──────────────────────────────────────────────┘
  │
  ▼
archived ◄─────────────────────────────────────────┘
```

---

## Error Codes

| Code | Description | Action |
|------|-------------|--------|
| `not_found` | Entity does not exist | Check ID with `list` command |
| `validation_error` | Invalid input value | Verify JSON format and enum values |
| `invalid_transition` | Invalid status transition | Check transition guards |
| `conflict` | Revision mismatch | Get latest state and retry |
| `dependency_blocked` | Dependency blocking | Check parent task |

---

## 関連資料

- [RUNBOOK.md](./RUNBOOK.md) - 詳細操作手順
- [agent-taskstate_mvp_spec.md](./agent-taskstate_mvp_spec.md) - MVP 仕様書
- [agent-taskstate_sqlite_spec.md](./agent-taskstate_sqlite_spec.md) - SQLite 仕様書

---

## 変更履歴

| 日付 | 変更内容 |
|-----|---------|
| 2026-03-07 | 初版作成 |