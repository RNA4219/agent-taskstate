---
intent_id: INT-001
owner: agent-taskstate-team
status: active
last_reviewed_at: 2025-03-07
next_review_due: 2025-04-07
---

# agent-taskstate Task Seed Template

## メタデータ

```yaml
task_id: YYYYMMDD-xx
repo: https://github.com/owner/agent-taskstate
base_branch: main
work_branch: feat/short-slug
priority: P1|P2|P3
langs: [python]
```

## Objective

{{一文で目的}}

## Scope

- In: {{対象(ディレクトリ/機能/CLI)を箇条書き}}
- Out: {{非対象(触らない領域)を箇条書き}}

## Requirements

- Behavior:
  - {{期待挙動1}}
  - {{期待挙動2}}
- I/O Contract:
  - Input: {{型/例}}
  - Output: {{型/例}}
- Constraints:
  - JSON契約 `{ok, data, error}` 遵守
  - typed_ref 形式使用
  - Lint/Type/Test はゼロエラー
- Acceptance Criteria:
  - {{検収条件1}}
  - {{検収条件2}}

## Affected Paths

- {{glob例: docs/src/**, tests/**, src/agent_taskstate.py}}

## Local Commands

```bash
# Python
ruff check . && black --check . && mypy src/ && pytest tests/ -v

# Fallback
python -m pytest tests/ -v --cov=src
```

## Deliverables

- PR: タイトル/要約/影響/ロールバック
  - 本文へ `Intent: INT-xxx` と `## EVALUATION` アンカーを明記
- Artifacts: 変更パッチ、テスト、必要ならREADME/CHANGELOG差分

---

## Plan

### Steps

1. 現状把握（対象ファイル列挙、既存テストとI/O確認）
2. テストを先に記述
3. 最小限の実装
4. テスト実行→通過確認
5. リファクタリング
6. ドキュメント更新（必要なら）

## Patch

***Provide a unified diff. Include full paths. New files must be complete.***

## Tests

### Outline

- Unit:
  - {{case-1: 入力→出力の最小例}}
  - {{case-2: エッジ/エラー例}}
- Integration:
  - {{代表シナリオ1つ}}

## Commands

### Run gates

```bash
pytest tests/ -v
ruff check src/ tests/
black --check src/ tests/
mypy src/
```

## Notes

### Rationale

- {{設計判断を1～2行}}

### Risks

- {{既知の制約/互換性リスク}}

### Follow-ups

- {{後続タスクあれば}}

---

## Template Usage

このテンプレートをコピーして `TASK.<slug>-MM-DD-YYYY.md` として保存：

```bash
# 例
TASK.task-create-test-03-07-2025.md
TASK.state-patch-conflict-03-07-2025.md
```