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

## [1.0.0] - 2026-03-09

### Added

- repo 同梱 Codex skill `$agent-taskstate-maintainer` を追加
- 人間向け README と Agent 向け README を分離し、`README-human.md` を追加
- `docs/kv-priority-roadmap/` の agent-taskstate 命名を整理

### Changed

- Agent README を `tracker-bridge-materials` と同系統の軽量導線へ再構成
- `context_bundle` の監査項目に合わせて schema / migration / README / skill 導線を更新
- テストコードの未使用 import / 変数を整理し、`ruff check src tests` を通過させた

### Fixed

- `typed_ref` の validator と formatter を修正し、既知 domain の canonical 4 セグメント形式を厳格化
- `context_bundle` の `selected_raw`、`metadata_json`、`diagnostics`、generator 監査情報の永続化漏れを修正
- `tracker_bridge` の canonical ref 検証、snapshot sync result、outbound status 反映を修正
- `pytest` の収集対象を調整し、未追跡の `workflow-cookbook/` が混ざらないようにした

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
