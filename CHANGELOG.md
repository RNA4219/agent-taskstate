---
intent_id: INT-001
owner: agent-taskstate-team
status: active
last_reviewed_at: 2025-03-07
next_review_due: 2025-04-07
---

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- 0001: MVP仕様書 (`docs/src/agent-taskstate_mvp_spec.md`) 追加
- 0002: 要件定義ペライチ (`docs/src/agent-taskstate_requirements_one_pager.md`) 追加
- 0003: SQLite仕様書 (`docs/src/agent-taskstate_sqlite_spec.md`) 追加
- 0004: CLI実装 (`docs/src/agent-taskstate_cli.py`) 追加
- 0005: 開発フロー定義 (`RUNBOOK.md`) 追加
- 0006: 受入基準 (`EVALUATION.md`) 追加
- 0007: チェックリスト (`CHECKLISTS.md`) 追加
- 0008: テスト設計 (`docs/tests/*.feature`) 追加
  - `task.feature`: Task管理テストシナリオ
  - `state.feature`: Task State管理テストシナリオ
  - `decision.feature`: Decision管理テストシナリオ
  - `question.feature`: Open Question管理テストシナリオ
  - `run.feature`: Run記録テストシナリオ
  - `context.feature`: Context Bundle管理テストシナリオ
  - `export.feature`: Export機能テストシナリオ
- 0009: プロジェクト概要 (`BLUEPRINT.md`) 追加
- 0010: 行動指針 (`GUARDRAILS.md`) 追加
- 0011: タスク分割ハブ (`HUB.codex.md`) 追加
- 0012: タスクシードテンプレート (`TASK.codex.md`) 追加
- 0013: プロジェクトREADME (`README.md`) 追加

## [0.1.0] - 2026-03-09

### Added

- 初版リリース
- MVP仕様書、要件定義、SQLite仕様書
- CLI実装 (Task/State/Decision/Question/Run/Context Bundle/Export)
- typed_ref 4セグメント正準形式対応
- ContextRebuildResolver 実装
- TrackerBridgeService 実装
- memx-core統合テスト追加

### Changed

- **BREAKING**: プロジェクト名を `workx` から `agent-taskstate` に変更
  - typed_refドメイン: `workx:*` → `agent-taskstate:*`
  - CLIコマンド: `workx` → `agent-taskstate`
  - DBパス: `~/.workx/workx.db` → `~/.agent-taskstate/agent-taskstate.db`

### Known Limitations

- API/MCPサーバーは未実装（将来フェーズ）
- GUI/Web UIは未実装
- 複数ユーザー対応なし

---

## Versioning Policy

- **Major**: 破壊的変更（CLI出力形式変更、DBスキーマ非互換）
- **Minor**: 機能追加（新コマンド、新エンティティ）
- **Patch**: バグ修正、ドキュメント更新

## Change Categories

- **Added**: 新機能
- **Changed**: 既存機能の変更
- **Deprecated**: 近く削除される機能
- **Removed**: 削除された機能
- **Fixed**: バグ修正
- **Security**: セキュリティ関連の修正