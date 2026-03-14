# agent-taskstate Checklists

本ドキュメントは agent-taskstate MVP のリリースおよびレビューに関するチェックリストを定義する。

---

## 1. Pre-Commit Checklist

コミット前に実施すること。

### 1.1 Code Quality

- [ ] `pytest tests/ -v` が全て通過している
- [ ] `ruff check src/ tests/` でエラーがない
- [ ] `black --check src/ tests/` でフォーマット違反がない
- [ ] `mypy src/` で型エラーがない（任意）

### 1.2 Documentation

- [ ] 変更内容が MVP Spec に反映されている（必要な場合）
- [ ] CLI --help が更新されている（コマンド追加/変更時）
- [ ] 破壊的変更がある場合、移行ガイドを記載

### 1.3 Commit Message

- [ ] プレフィックスが適切（feat/fix/chore/docs/test/spec）
- [ ] 変更内容が1行で理解できる
- [ ] 関連 Issue や Spec セクションへの参照がある（任意）

---

## 2. Pull Request Checklist

PR 作成時に確認すること。

### 2.1 Required

- [ ] テストが全て通過している
- [ ] 新規コードにテストが追加されている
- [ ] MVP Spec と実装が整合している
- [ ] エラーコードが `EVALUATION.md` の定義通り

### 2.2 Code Review

- [ ] 仕様書への参照がコメントにある（`Spec 5.1` 等）
- [ ] typed_ref 形式が正しく使用されている
- [ ] JSON 出力形式 `{ok, data, error}` を守っている
- [ ] 状態遷移ガードが仕様通り実装されている

### 2.3 PR Description Template

```markdown
## Summary
<!-- 変更内容を1-2文で -->

## Related Spec
<!-- 関連する仕様書セクション: Spec 5.1, SQLite Spec 7.2 等 -->

## Changes
- [ ] 変更点1
- [ ] 変更点2

## Test Plan
- [ ] 追加したテストケース
- [ ] 手動確認項目

## Checklist
- [ ] テスト通過
- [ ] Spec 整合
- [ ] ドキュメント更新（必要な場合）
```

---

## 3. Feature Completion Checklist

各機能の完了判定用チェックリスト。

### 3.1 Task Management

#### task create

- [ ] 必須フィールド指定で作成できる
- [ ] 必須フィールド欠落で `validation_error`
- [ ] 不正な kind で `validation_error`
- [ ] 不正な priority で `validation_error`
- [ ] 作成後の status が `draft`
- [ ] 返却値が `{ok: true, data: {task_id: ...}}`

#### task show

- [ ] 存在する ID で詳細取得できる
- [ ] 存在しない ID で `not_found`

#### task list

- [ ] 全件取得できる
- [ ] --status でフィルタできる
- [ ] --kind でフィルタできる
- [ ] --owner-type でフィルタできる
- [ ] --owner-id でフィルタできる

#### task update

- [ ] 各フィールドを更新できる
- [ ] 存在しない ID で `not_found`
- [ ] 不正な値で `validation_error`

#### task set-status

- [ ] 許可された遷移が成功する
- [ ] 許可されていない遷移で `invalid_transition`
- [ ] ガード条件違反で `invalid_transition`
- [ ] 例外遷移で理由メモが必須

### 3.2 Task State

#### state get

- [ ] 存在する task_id で取得できる
- [ ] revision が含まれている
- [ ] state 未作成の task で `not_found`

#### state put

- [ ] 新規作成できる（revision=1）
- [ ] 既存を上書きできる（revision=1 にリセット）

#### state patch

- [ ] revision 一致で更新できる
- [ ] revision 不一致で `conflict`
- [ ] 存在しない task で `not_found`
- [ ] 更新後の revision が +1 されている

### 3.3 Decision

#### decision add

- [ ] 必須フィールドで作成できる
- [ ] 作成時の status が `proposed`
- [ ] 存在しない task_id で `not_found`

#### decision list

- [ ] task 配下の decision 一覧を取得
- [ ] --status でフィルタできる

#### decision accept

- [ ] status が `accepted` になる
- [ ] 存在しない ID で `not_found`
- [ ] 既に `accepted` の場合は何もしない（冪等）

#### decision reject

- [ ] status が `rejected` になる
- [ ] 存在しない ID で `not_found`

### 3.4 Open Question

#### question add

- [ ] 必須フィールドで作成できる
- [ ] 作成時の status が `open`
- [ ] 存在しない task_id で `not_found`

#### question list

- [ ] task 配下の question 一覧を取得
- [ ] --status でフィルタできる
- [ ] --priority でフィルタできる

#### question answer

- [ ] answer が設定される
- [ ] status が `answered` になる
- [ ] 存在しない ID で `not_found`

#### question defer

- [ ] status が `deferred` になる
- [ ] --reason が設定される（指定時）

### 3.5 Run

#### run start

- [ ] 必須フィールドで作成できる
- [ ] 作成時の status が `running`
- [ ] started_at が設定される
- [ ] run_id が返る

#### run finish

- [ ] status が更新される
- [ ] ended_at が設定される
- [ ] output_ref が設定される（指定時）
- [ ] 存在しない run_id で `not_found`

### 3.6 Context Bundle

#### context build

- [ ] build_reason 指定で作成できる
- [ ] task 基本情報が含まれる
- [ ] 最新 task_state が含まれる
- [ ] accepted decisions が含まれる
- [ ] open な open_questions が含まれる
- [ ] evidence 含有条件が正しく動作する

#### context show

- [ ] bundle 詳細を取得できる
- [ ] 存在しない ID で `not_found`

### 3.7 Export

#### export task

- [ ] task が含まれる
- [ ] task_state が含まれる
- [ ] decisions[] が含まれる
- [ ] open_questions[] が含まれる
- [ ] runs[] が含まれる
- [ ] context_bundles[] が含まれる
- [ ] JSON ファイルが出力される

---

## 4. Release Checklist

リリース判定時に確認すること。

### 4.1 Quality Gate

- [ ] 全テストケースが通過している
- [ ] テストカバレッジが目標を達成している
  - 正常系: 100%
  - 異常系: 100%
  - ガード条件: 100%
  - 境界値: 80%以上
- [ ] lint/type check がエラーなし
- [ ] ドキュメントの lint がエラーなし

### 4.2 Acceptance Criteria

- [ ] AC-001: Task 作成が動作する
- [ ] AC-002: Task 一覧が動作する
- [ ] AC-003: Task 状態遷移が動作する
- [ ] AC-004: Task State 取得が動作する
- [ ] AC-005: Task State 更新が動作する
- [ ] AC-006: Decision 追加が動作する
- [ ] AC-007: Open Question 追加が動作する
- [ ] AC-008: Run 記録が動作する
- [ ] AC-009: Context Bundle 生成が動作する
- [ ] AC-010: JSON Export が動作する

### 4.3 Documentation

- [ ] MVP Spec が最新状態
- [ ] SQLite Spec が最新状態
- [ ] CLI --help が全コマンド対応
- [ ] CHANGELOG.md が更新されている
- [ ] 破壊的変更がある場合はマイグレーションガイド記載

### 4.4 Manual Verification

- [ ] 新規インストールで初期化できる
- [ ] 主要ワークフローを手動で実行できる
  - task 作成 → state 設定 → decision 追加 → context build
- [ ] エラーメッセージが理解可能
- [ ] 性能が体感1秒未満

### 4.5 Release Process

1. [ ] バージョン番号を決定（セマンティックバージョニング）
2. [ ] CHANGELOG.md にリリースノートを追加
3. [ ] タグを作成（`git tag v0.1.0`）
4. [ ] リリースコミットを作成
5. [ ] リリースアナウンス（必要な場合）

---

## 5. Review Checklist

コードレビュー時に確認すること。

### 5.1 Specification Alignment

- [ ] 実装が MVP Spec の定義通り
- [ ] 属性名・型が Spec と一致
- [ ] 状態遷移が Spec 7.2-7.4 と一致
- [ ] エラーコードが Spec 10.4 と一致

### 5.2 Design Principles

- [ ] Agent-First: 機械可読な出力
- [ ] Chat-History-Free: 状態で進行可能
- [ ] Append-Oriented: 履歴が残る（該当箇所）
- [ ] Loose Coupling: typed_ref で疎結合

### 5.3 Code Quality

- [ ] 関数が単一責務
- [ ] 複雑度が適切（ネスト3以下推奨）
- [ ] 重複コードがない
- [ ] 適切なエラーハンドリング

### 5.4 Test Quality

- [ ] テストケースが仕様をカバー
- [ ] アサーションが十分
- [ ] テスト名が意図を表している
- [ ] テスト間の依存がない

### 5.5 Security

- [ ] SQL インジェクション対策（パラメータ化クエリ）
- [ ] パス操作の安全性
- [ ] 機密情報のハードコードなし

---

## 6. Incident Response Checklist

問題発生時の対応手順。

### 6.1 Bug Report

バグ報告時に確認すること：

- [ ] 再現手順が明確
- [ ] 期待動作が明確
- [ ] 実際の動作が明確
- [ ] 環境情報（OS, Python version）

### 6.2 Bug Fix

バグ修正時に確認すること：

- [ ] 根本原因を特定
- [ ] 修正用テストケースを追加
- [ ] 修正が他に影響しないことを確認
- [ ] CHANGELOG に記録

### 6.3 Hotfix

緊急修正時の手順：

1. [ ] 影響範囲を最小限に特定
2. [ ] 修正を実装
3. [ ] 最小限のテストで確認
4. [ ] リリース
5. [ ] 事後レビューで根本対応を検討

---

## 7. Maintenance Checklist

定期メンテナンス用。

### 7.1 Weekly

- [ ] テスト実行時間の確認
- [ ] カバレッジ推移の確認
- [ ] open issue/pr の確認

### 7.2 Monthly

- [ ] ドキュメントの陳腐化確認
- [ ] 依存パッケージの更新確認
- [ ] パフォーマンス劣化の確認

### 7.3 Per Release

- [ ] CHANGELOG 整理
- [ ] 非推奨機能の削除検討
- [ ] 将来バージョンの計画更新

---

## 8. Template: Change Log Entry

CHANGELOG.md への追記フォーマット。

```markdown
## [Unreleased]

### Added
- 0001: 新機能の説明 [#issue] (author)

### Changed
- 0002: 変更内容の説明

### Fixed
- 0003: バグ修正の説明

### Deprecated
- 0004: 非推奨になった機能
```

リリース時：

```markdown
## [0.1.0] - 2025-MM-DD

### Added
- 0001: Task 作成・更新・状態遷移機能
- 0002: Task State 管理（optimistic lock）
- 0003: Decision 追加・承認・拒否
...
```