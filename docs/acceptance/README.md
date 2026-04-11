---
intent_id: INT-001
owner: agent-taskstate
status: active
last_reviewed_at: 2026-04-11
next_review_due: 2026-05-11
---

# Acceptance Records

`docs/acceptance/` は agent-taskstate の検収記録を残す場所です。

## 使い方

1. [ACCEPTANCE_TEMPLATE.md](ACCEPTANCE_TEMPLATE.md) を複製する
2. `AC-YYYYMMDD-xx.md` 形式で保存する
3. front matter と各見出しを埋める
4. PR 本文の `Acceptance Record` からこのファイルへリンクする

## 命名規則

- `AC-YYYYMMDD-xx.md`
- 例: `AC-20260411-01.md`

## 必須項目

- front matter
  - `acceptance_id`
  - `task_id`（必要な場合）
  - `intent_id`
  - `owner`
  - `status`: `approved` | `rejected` | `draft`
  - `reviewed_at`
  - `reviewed_by`
- 本文見出し
  - `## Scope`
  - `## Acceptance Criteria`
  - `## Evidence`
  - `## Verification Result`

## 検証

```sh
pytest -q
```

## 参照

- [../CHECKLISTS.md](../CHECKLISTS.md) - Release Checklist
- [../RUNBOOK.md](../RUNBOOK.md) - Phase 7: 受入確認
- [../EVALUATION.md](../EVALUATION.md) - KPI 定義