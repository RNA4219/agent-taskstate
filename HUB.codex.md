---
intent_id: INT-001
owner: agent-taskstate-team
status: active
last_reviewed_at: 2025-03-07
next_review_due: 2025-04-07
---

# agent-taskstate HUB

リポジトリ内の仕様・運用MDを集約し、エージェントがタスクを自動分割できるようにするハブ定義。

## 1. 目的

- リポジトリ配下の計画資料から作業ユニットを抽出し、優先度順に配列
- 生成されたタスクリストを Task Seed へマッピング
- ドキュメント間の依存関係を明確化

## 2. 入力ファイル分類

| ファイル | 役割 | 優先度 |
|---------|------|-------|
| `BLUEPRINT.md` | 要件・制約・背景 | 高 |
| `GUARDRAILS.md` | ガードレール/行動指針 | 高 |
| `RUNBOOK.md` | 開発フロー・手順 | 中 |
| `EVALUATION.md` | 受け入れ基準・品質指標 | 中 |
| `CHECKLISTS.md` | リリース/レビュー確認項目 | 低 |
| `docs/src/*.md` | MVP仕様書・SQLite仕様書 | 高 |
| `docs/tests/*.feature` | テストシナリオ（Gherkin） | 高 |
| `CHANGELOG.md` | 完了タスクと履歴の記録 | 中 |

補完資料:

- `README.md`: リポジトリ概要と参照リンク
- `TASK.codex.md`: タスクシードテンプレート
- `docs/src/agent-taskstate_cli.py`: CLI実装（単一ファイルMVP）

更新日: 2025-03-07

## 3. ドキュメント依存関係

```
BLUEPRINT.md (要件)
    │
    ├──→ docs/src/agent-taskstate_mvp_spec.md (MVP仕様)
    │        │
    │        ├──→ docs/src/agent-taskstate_sqlite_spec.md (DB仕様)
    │        │
    │        └──→ docs/tests/*.feature (テストシナリオ)
    │
    ├──→ EVALUATION.md (受入基準)
    │
    └──→ RUNBOOK.md (開発フロー)
             │
             └──→ CHECKLISTS.md (チェックリスト)

GUARDRAILS.md (行動指針)
    │
    └──→ 全ドキュメントに適用
```

## 4. タスク分割フロー

1. **スキャン**: ルートと `docs/` 配下を再帰探索
2. **優先度抽出**: Front matter の `priority`, `status` を確認
3. **依存解決**: ドキュメント間の参照関係を解析
4. **粒度調整**: 作業ユニットを `<= 0.5d` 目安に分割
5. **テンプレート投影**: `TASK.codex.md` 形式へ変換
6. **出力整形**: 優先度・依存順にソート

## 5. Task Status & Blockers

```yaml
許容ステータス:
  - [] or [ ]: 未着手・未割り振り
  - planned: バックログ
  - active: 優先キュー入り（担当/期日付き）
  - in_progress: 着手中
  - reviewing: レビュー待ち
  - blocked: ブロック中
  - done: 完了

標準遷移:
  planned → active → in_progress → reviewing → done

例外遷移:
  in_progress → blocked → in_progress
```

## 6. 現在のタスク一覧

### 未着手

- [ ] docs/tests/*.feature を pytest テストコードに変換
- [ ] docs/src/agent-taskstate_cli.py と仕様書の整合性確認
- [ ] CI/CD パイプライン設定（GitHub Actions）

### 進行中

- [x] BLUEPRINT.md 作成
- [x] GUARDRAILS.md 作成
- [x] HUB.codex.md 作成
- [x] RUNBOOK.md 作成
- [x] EVALUATION.md 作成
- [x] CHECKLISTS.md 作成
- [x] docs/tests/*.feature テスト設計

### 完了

- [x] docs/src/ 要件定義ファイル確認

## 7. 出力例（Task Seed）

```yaml
- task_id: 20250307-01
  source: docs/tests/task.feature#L1-50
  objective: task create コマンドのテスト実装
  scope:
    in: [tests/test_task.py]
    out: [src/agent_taskstate.py]
  requirements:
    behavior:
      - 必須フィールド指定で task 作成できる
      - バリデーションエラーが正しく返る
    constraints:
      - MVP Spec 6.2 準拠
  commands:
    - pytest tests/test_task.py -v
  dependencies: []
```