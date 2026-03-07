# agent-taskstate

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Agent-First Task State Management Tool**

長期タスクの進行状態を構造化して保持し、エージェントまたは人間が毎回必要な文脈を再構成して次の一手を出せるようにするためのツール。

<!-- LLM-BOOTSTRAP v1 -->
読む順番:

1. BLUEPRINT.md …… 要件・制約・背景
2. docs/src/agent-taskstate_mvp_spec.md …… MVP仕様書
3. GUARDRAILS.md …… 行動指針・開発原則

フォーカス手順:

- 目的に応じて上記ドキュメントを選択
- テストシナリオは `docs/tests/*.feature` を参照
<!-- /LLM-BOOTSTRAP -->

## 概要

agent-taskstate は、チャット履歴や KV キャッシュに依存せず、タスクの進行状態を構造化データとして保持するローカル状態管理ツール。

**目的**: 会話を覚えさせるのではなく、Task / State / Decision / Question / ContextBundle を明示的に持たせることで、長い仕事を再構成可能にする。

## 特徴

- **Agent-First**: 機械が叩きやすい安定した JSON 入出力
- **Chat-History-Free**: チャット履歴ではなく状態で進行
- **Append-Oriented**: 履歴を残す設計
- **Local-First**: SQLite ベース、オフライン動作可能
- **Loose Coupling**: typed_ref による疎結合連携

## クイックスタート

```bash
# Task 作成
agent-taskstate task create --kind feature --title "新機能" --goal "実装する" \
  --priority high --owner-type agent --owner-id agent-001

# State 設定
agent-taskstate state put --task <task_id> --file state.json

# Context Bundle 生成
agent-taskstate context build --task <task_id> --reason normal

# Export
agent-taskstate export task --task <task_id> --output export.json
```

## ドキュメント

| ドキュメント | 説明 |
|-------------|------|
| [BLUEPRINT.md](BLUEPRINT.md) | プロジェクト概要・要件・制約 |
| [GUARDRAILS.md](GUARDRAILS.md) | 行動指針・開発原則 |
| [RUNBOOK.md](RUNBOOK.md) | SDD+TDD開発フロー |
| [EVALUATION.md](EVALUATION.md) | 受入基準・評価観点 |
| [CHECKLISTS.md](CHECKLISTS.md) | リリース・レビューチェックリスト |
| [HUB.codex.md](HUB.codex.md) | タスク分割ハブ |
| [CHANGELOG.md](CHANGELOG.md) | 変更履歴 |

### 仕様書

| ドキュメント | 説明 |
|-------------|------|
| [docs/src/agent-taskstate_mvp_spec.md](docs/src/agent-taskstate_mvp_spec.md) | MVP仕様書 |
| [docs/src/agent-taskstate_requirements_one_pager.md](docs/src/agent-taskstate_requirements_one_pager.md) | 要件定義ペライチ |
| [docs/src/agent-taskstate_sqlite_spec.md](docs/src/agent-taskstate_sqlite_spec.md) | SQLiteスキーマ仕様 |

### テスト設計

| ドキュメント | 説明 |
|-------------|------|
| [docs/tests/task.feature](docs/tests/task.feature) | Task管理テストシナリオ |
| [docs/tests/state.feature](docs/tests/state.feature) | Task State管理テストシナリオ |
| [docs/tests/decision.feature](docs/tests/decision.feature) | Decision管理テストシナリオ |
| [docs/tests/question.feature](docs/tests/question.feature) | Open Question管理テストシナリオ |
| [docs/tests/run.feature](docs/tests/run.feature) | Run記録テストシナリオ |
| [docs/tests/context.feature](docs/tests/context.feature) | Context Bundle管理テストシナリオ |
| [docs/tests/export.feature](docs/tests/export.feature) | Export機能テストシナリオ |

## コアエンティティ

```
Task (到達目標)
├── Task State (現在状態ダッシュボード)
├── Decision[] (意思決定ログ)
├── Open Question[] (未解決論点)
├── Run[] (実行記録)
└── Context Bundle[] (状態再構成用入力束)
```

## 状態遷移

```
draft → ready → in_progress → review → done → archived
                    ↓
                blocked
```

## CLI コマンド

```bash
# Task 管理
agent-taskstate task create/show/list/update/set-status

# Task State 管理
agent-taskstate state get/put/patch

# Decision 管理
agent-taskstate decision add/list/accept/reject

# Open Question 管理
agent-taskstate question add/list/answer/defer

# Run 記録
agent-taskstate run start/finish

# Context Bundle 管理
agent-taskstate context build/show

# Export
agent-taskstate export task
```

## 開発

```bash
# テスト実行
pytest tests/ -v

# Lint
ruff check src/ tests/

# Format
black src/ tests/

# Type check
mypy src/
```

## ライセンス

MIT License