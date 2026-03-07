---
intent_id: INT-001
owner: agent-taskstate-team
status: active
last_reviewed_at: 2025-03-07
next_review_due: 2025-04-07
---

# agent-taskstate Guardrails & 行動指針

リポジトリ運用時に守るべき原則と振る舞いを体系化する。

## 目的

- リポジトリ内の既存ルール（型安全、JSON契約、typed_ref形式）を自動検出し、厳密に遵守する。
- 変更は最小差分で行い、Public API を破壊しない。不可避の場合のみ短い移行メモを添付する。
- 応答は簡潔で実務に直結させ、冗長な説明や代替案の羅列は避ける。
- 実装時はテスト駆動開発を基本とし、テストを先に記述する。

## スコープとドキュメント

1. 目的を一文で定義し、誰のどの課題をなぜ今扱うかを明示する。
2. Scope を固定し、In/Out の境界を先に決めて記録する。
3. I/O 契約（入力/出力の型・例）を `BLUEPRINT.md` に整理する。
4. Acceptance Criteria（検収条件）を `EVALUATION.md` に列挙する。
5. 開発フロー（準備→実行→確認）を `RUNBOOK.md` に記す。
6. `HUB.codex.md` の自動タスク分割フローに従い、タスク化した内容を Task Seed へマッピングして配布する。
7. 完了済みタスクは `CHANGELOG.md` へ移し、履歴を更新する。
8. テスト/型/lint/CI の実行結果を確認し、`CHECKLISTS.md` でリリース可否を判断する。

## 設計原則

### Agent-First

- 人間向け UX よりも、**機械が叩きやすい安定した入出力**を優先する
- すべての操作は **明示的・決定的・JSON 互換** であることを目指す
- エージェントは agent-taskstate を「考える存在」ではなく、**状態を読むための作業台**として使う

### Chat-History-Free

- チャット履歴を正本にしない
- `task_state` と `context_bundle` により、会話継続ではなく **状態再構成** で進める

### Append-Oriented

- `decision`, `open_question`, `run`, `context_bundle` は履歴を残す
- 変更は上書きよりも「追加と状態更新」を優先する

### Loose Coupling

- memx や tracker とは typed_ref による疎結合連携を行う
- DB 横断 FK は持たない

## 実装原則

### 型安全

- 新規・変更シグネチャには必ず型を付与し、Optional/Union は必要最小限に抑える。
- 列挙値は `Literal` 型または定数セットで定義する。

```python
from typing import Literal

TaskKind = Literal["bugfix", "feature", "research"]
TaskStatus = Literal["draft", "ready", "in_progress", "blocked", "review", "done", "archived"]
```

### JSON 契約

- 全 CLI コマンドは `{ok, data, error}` 形式を出力する。
- 正常時は `ok: true, data: {...}, error: null`。
- エラー時は `ok: false, data: null, error: {code, message}`。

### typed_ref 形式

- 外部参照は必ず `<namespace>:<entity_type>:<id>` 形式を使用する。
- 例: `agent-taskstate:task:01H...`, `memx:evidence:01H...`, `tracker:jira:PROJ-123`

### 状態遷移ガード

- 状態遷移は仕様書（MVP Spec 7.2-7.4）に定義されたガード条件を厳守する。
- ガード違反時は `invalid_transition` エラーを返す。

### 楽観ロック

- `task_state` 更新時は必ず `expected_revision` を要求する。
- 不一致時は `conflict` エラーを返す。
- 自動マージは行わない。

### インポート順序

- 標準ライブラリ → 外部依存 → 内部モジュールの順で空行区切りとする。

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typing import Any, Dict, Optional

from .models import Task, TaskState
```

### スコープ上限

- 1 回の変更は合計 100 行または 2 ファイルまで。
- 単一ファイルが 400 行を超える場合は機能単位で分割を検討する。

### 削除・保管ルール

- task は物理削除せず `archived` とする。
- decision は削除せず `superseded` / `rejected` を使う。
- open_question は `answered` / `deferred` / `invalid` を使う。
- run / context_bundle は削除しない（追記のみ）。

## プロセスと自己検証

### TDD サイクル

1. テストを先に書く（Red）
2. 最小限の実装を行う（Green）
3. リファクタリングする（Refactor）

### コミット前確認

- `pytest tests/ -v` が全て通過している
- `ruff check src/ tests/` でエラーがない
- `black --check src/ tests/` でフォーマット違反がない
- `mypy src/` で型エラーがない

### 競合解消

- 競合解消時は双方の意図を最小限で統合し、判断をコメントに1行で記す。

### 性能目標

- 主要操作の実行時間は体感1秒未満を目標とする。
- 実行コストやレイテンシへの影響は ±5% 以内を目標とする。

## 例外処理

### スコープ上限超過

- スコープ上限を超える作業が必要な場合は、作業を分割してタスク化を提案する。

### 破壊的変更

- 破壊的変更が不可避な場合は、移行期間やフラグ運用を明記したメモを添付する。
- CLI 出力形式の変更は、後方互換性を維持するか、明示的なバージョン指定を必要とする。

### セキュリティ

- 秘密情報は扱わず、必要な場合は環境変数やサンプル参照に限定する。
- SQL インジェクション対策として、パラメータ化クエリを使用する。

## テスト設計ガイドライン

### テスト分類

| 分類 | 内容 | 優先度 |
|-----|------|-------|
| Happy Path | 正常フロー全通し | P0 |
| Guard Conditions | 状態遷移ガード違反 | P0 |
| Validation | 入力バリデーション | P0 |
| Edge Cases | 境界値・空値・最大値 | P1 |
| Error Recovery | エラー復旧・冪等性 | P1 |
| Concurrency | 競合・楽観ロック | P2 |

### テスト命名規約

```python
class TestTaskCreate:
    """task create コマンドのテスト"""

    def test_create_with_required_fields(self):
        """必須フィールドのみで作成できる"""
        pass

    def test_create_without_kind_returns_validation_error(self):
        """kind 未指定時は validation_error"""
        pass
```

### テストコードと仕様のトレーサビリティ

```python
def test_task_create_requires_kind(self):
    """Spec 6.2: task create --kind is required"""
    # MVP Spec Section 7.4: ready遷移ガード - kindが設定済み
    pass
```

## リマインダー

- 変更は常にテストから着手し、最小の成功条件を先に満たす。
- 全ての関係者が同じ期待値を共有できるよう、上記ドキュメントを更新し続ける。
- 仕様書との整合性を常に確認し、乖離がある場合は即座に修正または文書更新を行う。

<!-- guardrails:yaml
forbidden_paths:
  - ".agent-taskstate/*.db"
  - "*.env"
require_human_approval:
  - "docs/src/*.md"
slo:
  operation_latency_p95_ms: 1000
  test_coverage_min: 0.90
  change_failure_rate_max: 0.10
-->