# agent-taskstate MVP 実装とドキュメントの差分分析

作成日: 2026-03-07
更新日: 2026-03-07

## 1. 概要

本資料は `agent-taskstate` プロジェクトの現状実装とドキュメントの差分を整理し、RUNBOOK 再作成の基礎資料とする。

---

## 2. ドキュメント一覧

### 2.1 docs/ 直下の仕様書

| ファイル | 内容 | 状態 |
|---------|------|------|
| `agent-taskstate_requirements_one_pager.md` | 要件定義（ペライチ） | 完備 |
| `agent-taskstate_mvp_spec.md` | MVP 仕様書 | **更新済** (metadata, created_at 追記) |
| `agent-taskstate_sqlite_spec.md` | SQLite 仕様書 | 完備 |
| `agent-taskstate_cli.py` | CLI 実装（単一ファイル MVP） | 実装済 |
| `RUNBOOK.md` | 運用手順書 | **新規作成済** |
| `CHECKLISTS.md` | チェックリスト | **新規作成済** |
| `IMPLEMENTATION_VS_DOCS_DIFF.md` | 本資料 | - |

### 2.2 docs/src/ 配下

`docs/src/` 配下にも同様のファイルが存在。内容は同一。

---

## 3. 仕様書更新内容（2026-03-07）

MVP Spec に以下の属性を追記し、SQLite Spec と整合させた：

| エンティティ | 追記属性 |
|-------------|---------|
| Task | `metadata` (任意) |
| Task State | `created_at` |
| Decision | `metadata` (任意) |
| Open Question | `metadata` (任意) |
| Run | `metrics` (任意), `metadata` (任意) |
| Context Bundle | `metadata` (任意) |

---

## 3. workflow-cookbook テンプレートとの対比

### 3.1 必須ドキュメントの有無

| workflow-cookbook テンプレート | agent-taskstate 状態 | 備考 |
|-------------------------------|---------------------|------|
| `BLUEPRINT.md` | **未作成** | Problem Statement, Scope, Constraints, I/O Contract が必要 |
| `RUNBOOK.md` | **未作成** | Execute, Observability, Confirm, Rollback 手順が必要 |
| `EVALUATION.md` | **未作成** | Acceptance Criteria, KPIs, Test Outline が必要 |
| `GUARDRAILS.md` | **未作成** | 実装原則、Birdseye 連携制約が必要 |
| `HUB.codex.md` | **未作成** | タスク分割ハブが必要 |
| `CHECKLISTS.md` | **未作成** | Development, PR/Review, Release チェックリストが必要 |
| `CHANGELOG.md` | **未作成** | 変更履歴が必要 |
| `CODE_OF_CONDUCT.md` | **未作成** | 行動規範が必要 |
| `SECURITY.md` | **未作成** | セキュリティポリシーが必要 |

### 3.2 CI/CD インフラ

| workflow-cookbook テンプレート | agent-taskstate 状態 | 備考 |
|-------------------------------|---------------------|------|
| `.github/workflows/` | **未整備** | governance-gate.yml, python-ci.yml 等が必要 |
| `tools/codemap/` | **未整備** | Birdseye 更新ツールが必要 |
| `tools/perf/` | **未整備** | メトリクス収集ツールが必要 |
| `docs/birdseye/` | **未整備** | コードマップ JSON が必要 |

---

## 4. 実装とドキュメントの整合性確認

### 4.1 CLI コマンド実装状況

| カテゴリ | コマンド | MVP Spec | 実装状態 | 備考 |
|---------|---------|----------|---------|------|
| **task** | `create` | 必須 | **実装済** | ULID 自動生成、status=draft |
| | `show` | 必須 | **実装済** | JSON 出力対応 |
| | `list` | 必須 | **実装済** | フィルタ対応 |
| | `update` | 必須 | **実装済** | 各フィールド更新可 |
| | `set-status` | 必須 | **実装済** | 遷移ガード実装済 |
| **state** | `get` | 必須 | **実装済** | revision 含む |
| | `put` | 必須 | **実装済** | 初期作成用 |
| | `patch` | 必須 | **実装済** | optimistic lock 実装済 |
| **decision** | `add` | 必須 | **実装済** | proposed 状態で作成 |
| | `list` | 必須 | **実装済** | ステータスフィルタ可 |
| | `accept` | 必須 | **実装済** | accepted に遷移 |
| | `reject` | 必須 | **実装済** | rejected に遷移 |
| **question** | `add` | 必須 | **実装済** | open 状態で作成 |
| | `list` | 必須 | **実装済** | ステータス/優先度フィルタ可 |
| | `answer` | 必須 | **実装済** | answered に遷移 |
| | `defer` | 必須 | **実装済** | deferred に遷移 |
| **run** | `start` | 必須 | **実装済** | ULID 生成、status=running |
| | `finish` | 必須 | **実装済** | 終了時刻・出力記録 |
| **context** | `build` | 必須 | **実装済** | evidence 条件分岐実装済 |
| | `show` | 必須 | **実装済** | JSON 出力 |
| **export** | `task` | 必須 | **実装済** | 全エンティティ JSON 出力 |

### 4.2 データモデル整合性

| エンティティ | SQLite Spec | 実装状態 | 差分 |
|-------------|-------------|---------|------|
| `task` | 定義済 | **整合** | parent_task_id FK 実装済 |
| `task_state` | 定義済 | **整合** | revision, optimistic lock 実装済 |
| `decision` | 定義済 | **整合** | supersedes_decision_id 実装済 |
| `open_question` | 定義済 | **整合** | priority, status 列挙実装済 |
| `run` | 定義済 | **整合** | metrics_json, metadata_json 実装済 |
| `context_bundle` | 定義済 | **整合** | expected_output_schema 実装済 |
| `schema_version` | 定義済 | **整合** | version=1 で初期化 |

### 4.3 状態遷移ガード実装状況

| Status | 遷移条件 | MVP Spec | 実装状態 |
|--------|---------|----------|---------|
| `ready` | goal 非空, done_when 1件以上, kind 設定済 | 必須 | **実装済** |
| `in_progress` | task_state 存在, current_step 非空 | 必須 | **実装済** |
| `review` | high priority open_question 0件, decision 1件以上 | 必須 | **実装済** |
| `done` | done_when 全て満たす, current_summary あり, review 通過済 | 必須 | **実装済** |

### 4.4 Context Bundle 生成ロジック

| 条件 | MVP Spec | 実装状態 |
|-----|----------|---------|
| 常に含める: task 基本情報 | 必須 | **実装済** |
| 常に含める: 最新 task_state | 必須 | **実装済** |
| 常に含める: accepted decisions | 必須 | **実装済** |
| 常に含める: open open_questions | 必須 | **実装済** |
| 常に含める: done_when | 必須 | **実装済** |
| 常に含める: current_step | 必須 | **実装済** |
| 条件付き: proposed decisions | 必須 | **実装済** |
| 条件付き: evidence_refs | 必須 | **実装済** |
| evidence 条件分岐 | 必須 | **実装済** |

---

## 5. 未実装・未整備項目

### 5.1 機能面

| 項目 | 重要度 | 備考 |
|-----|--------|------|
| 例外遷移の理由メモ必須チェック | 中 | `draft->archived`, `done->in_progress` |
| Import 機能 | 低 | MVP 非必須だが Export と対で推奨 |
| ULID 検証 | 低 | 形式チェック実装済みだが外部ライブラリ依存なし |

### 5.2 運用・品質面

| 項目 | 重要度 | 備考 |
|-----|--------|------|
| テストコード | 高 | 現在テストなし |
| CI/CD パイプライン | 高 | GitHub Actions 未整備 |
| 型チェック (mypy) | 中 | 型ヒントありだが検証なし |
| Lint (ruff/black) | 中 | コード品質確認なし |
| エラーハンドリング強化 | 中 | 一部 SQLite エラーが素通り |

### 5.3 ドキュメント面

| 項目 | 重要度 | 備考 |
|-----|--------|------|
| BLUEPRINT.md | 高 | プロジェクト概要なし |
| RUNBOOK.md | 高 | 運用手順なし |
| EVALUATION.md | 高 | 受け入れ基準なし |
| GUARDRAILS.md | 中 | 実装ガイドラインなし |
| CHANGELOG.md | 中 | 変更履歴なし |
| API/MCP 仕様書 | 低 | 将来拡張用 |

---

## 6. 出力契約確認

### 6.1 JSON 出力形式

**Spec:**
```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

**実装:** 整合

### 6.2 エラーコード

| Spec コード | 実装状態 |
|------------|---------|
| `not_found` | **実装済** |
| `validation_error` | **実装済** |
| `invalid_transition` | **実装済** |
| `conflict` | **実装済** (revision mismatch) |
| `dependency_blocked` | **未使用** (将来用) |

---

## 7. 非機能要件確認

| 要件 | Spec | 実装状態 | 備考 |
|-----|------|---------|------|
| SQLite 単体動作 | 必須 | **OK** | 外部依存なし |
| オフライン利用 | 必須 | **OK** | ローカル DB のみ |
| 単一ユーザー前提 | 必須 | **OK** | 認証なし |
| 体感 1 秒未満 | 必須 | **確認必要** | 性能テスト未実施 |
| JSON Export | 必須 | **OK** | 実装済 |
| CLI first | 必須 | **OK** | API/MCP 未実装 |

---

## 8. MVP 完了条件確認

| 条件 | 状態 |
|-----|------|
| task を作成できる | **OK** |
| task_state を作成・更新できる | **OK** |
| decision を追加し、accept / reject できる | **OK** |
| open question を追加し、answer / defer できる | **OK** |
| run を開始・終了できる | **OK** |
| context bundle を生成・参照できる | **OK** |
| 生成した context bundle を見て、人間または LLM が次の一手を出せる | **確認必要** |
| task 単位の JSON export ができる | **OK** |

---

## 9. 推奨アクション

### 9.1 即時対応

1. **BLUEPRINT.md 作成** - プロジェクト概要と制約の明文化
2. **RUNBOOK.md 作成** - CLI 操作手順の文書化
3. **EVALUATION.md 作成** - 受け入れ基準とテスト観点の明文化
4. **テストコード作成** - pytest による基本テスト

### 9.2 短期対応

5. **CHECKLISTS.md 作成** - リリースチェックリスト
6. **CHANGELOG.md 作成** - 変更履歴
7. **CI/CD 整備** - GitHub Actions 基本構成

### 9.3 中期対応

8. **GUARDRAILS.md 作成** - 実装ガイドライン
9. **API 仕様書** - FastAPI 化時の OpenAPI spec
10. **Birdseye 整備** - コードマップ生成

---

## 10. 次ステップ

本資料を基に、以下の順で RUNBOOK を再作成する：

1. CLI インストール・初期化手順
2. 基本 CRUD 操作（task, state, decision, question, run, context）
3. Export 手順
4. トラブルシューティング
5. 将来拡張ポイント