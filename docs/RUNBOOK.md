# agent-taskstate Development Runbook

SDD (Specification-Driven Development) と TDD (Test-Driven Development) を統合した開発ワークフロー。

---

## 1. 概要

本 Runbook は、仕様書を「正」とし、テストを「実行可能な仕様」として扱う開発プロセスを定義する。

```
仕様書 → テストケース → 実装 → 検証 → 仕様書更新
    ↑___________________________________|
```

---

## 2. フェーズ概観

| フェーズ | 入力 | 出力 | 所要時間の目安 |
|---------|------|------|---------------|
| 1. 要件分析 | ユーザー要求 | Requirements One-Pager | 半日〜1日 |
| 2. 仕様策定 | Requirements One-Pager | MVP Spec / SQLite Spec | 1〜2日 |
| 3. テスト設計 | MVP Spec | Test Cases (Gherkin形式) | 半日 |
| 4. テスト実装 | Test Cases | テストコード (Red) | 各ケース数分 |
| 5. 実装 | テストコード | 本体コード (Green) | 各機能数十分〜数時間 |
| 6. リファクタリング | 動作するコード | 整理されたコード | 適宜 |
| 7. 受入確認 | 全テスト通過 | 受入済み機能 | 各機能数分 |

---

## 3. フェーズ詳細

### Phase 1: 要件分析

#### 入力
- ユーザーからの依頼
- ビジネスコンテキスト
- 既存システムの制約

#### 手順
1. ユーザー要求をヒアリングまたは文書から抽出
2. 目的・スコープ・非ゴールを明確化
3. `docs/src/<project>_requirements_one_pager.md` を作成
4. 用語定義・前提条件を整理

#### 出力物
- `docs/src/<project>_requirements_one_pager.md`
- 用語集エントリ（必要に応じて）

#### 完了条件
- [ ] 目的が1文で表現できる
- [ ] スコープ（含む/含まない）が明確
- [ ] コア概念が5つ以内に整理されている
- [ ] 非機能要件が列挙されている

---

### Phase 2: 仕様策定

#### 入力
- Requirements One-Pager

#### 手順
1. ドメインモデルを定義（エンティティ・値オブジェクト）
2. 各エンティティの必須属性・制約を列挙
3. 状態遷移図を作成（status, allowed transitions）
4. CLI/API インターフェースを定義
5. `docs/src/<project>_mvp_spec.md` を作成
6. 永続化が必要な場合、`docs/src/<project>_sqlite_spec.md` を作成

#### 出力物
- `docs/src/<project>_mvp_spec.md`
- `docs/src/<project>_sqlite_spec.md`（必要に応じて）

#### 完了条件
- [ ] 全エンティティの属性が型付きで定義されている
- [ ] 状態遷移の許可/例外が網羅されている
- [ ] CLIコマンド一覧が完了している
- [ ] 入出力スキーマ（JSON形式）が定義されている
- [ ] エラーコードが列挙されている

---

### Phase 3: テスト設計

#### 入力
- MVP Spec

#### 手順
1. 各 CLI コマンドについて、正常系・異常系のシナリオを列挙
2. 状態遷移ガード条件をテストシナリオ化
3. Gherkin 形式（Given-When-Then）でテストケースを記述
4. `docs/tests/<feature>.feature` ファイルを作成

#### テストケース分類

| 分類 | 内容 | 優先度 |
|-----|------|-------|
| Happy Path | 正常フロー全通し | P0 |
| Guard Conditions | 状態遷移ガード違反 | P0 |
| Validation | 入力バリデーション | P0 |
| Edge Cases | 境界値・空値・最大値 | P1 |
| Error Recovery | エラー復旧・冪等性 | P1 |
| Concurrency | 競合・楽観ロック | P2 |

#### Gherkin テンプレート

```gherkin
Feature: <機能名>

  Scenario: <シナリオ名>
    Given <前提条件>
    When <操作>
    Then <期待結果>

  Scenario: <異常系シナリオ名>
    Given <前提条件>
    When <操作>
    Then <エラーコード> が返る
```

#### 出力物
- `docs/tests/*.feature` ファイル群

#### 完了条件
- [ ] 全 CLI コマンドに最低1つの Happy Path がある
- [ ] 全エラーコードに対応するテストシナリオがある
- [ ] 状態遷移ガードがテストケース化されている
- [ ] 楽観ロック（revision）の競合ケースがある

---

### Phase 4: テスト実装 (Red)

#### 入力
- `.feature` ファイル
- MVP Spec

#### 手順
1. テストファイル `tests/test_<module>.py` を作成
2. `.feature` の各シナリオを pytest テスト関数に変換
3. テストを実行 → **全て失敗することを確認 (Red)**
4. 失敗理由が「未実装」であることを確認

#### テストコード規約

```python
# tests/test_task.py

class TestTaskCreate:
    """task create コマンドのテスト"""

    def test_create_with_required_fields(self, tmp_path):
        """必須フィールドのみで作成できる"""
        # Given: 空のDB
        # When: task create を実行
        # Then: ok=true, task_id が返る

    def test_create_without_kind_returns_validation_error(self, tmp_path):
        """kind 未指定時は validation_error"""
        # Given: 空のDB
        # When: kind 無しで create
        # Then: error.code = validation_error
```

#### 出力物
- `tests/test_*.py` ファイル群

#### 完了条件
- [ ] 全テストケースが実装されている
- [ ] テスト実行で全て失敗 (Red) している
- [ ] 失敗理由が仕様に基づくものである

---

### Phase 5: 実装 (Green)

#### 入力
- テストコード
- MVP Spec
- SQLite Spec

#### 手順
1. テストを1つ選ぶ
2. 最小限の実装を行う
3. テスト実行 → 通過することを確認 (Green)
4. 次のテストへ進む
5. 全テストが通るまで繰り返す

#### 実装規約

- 仕様書の属性名・型を厳守
- エラーコードは仕様書の定義を使用
- JSON 出力形式 `{ok, data, error}` を守る
- typed_ref 形式 `<namespace>:<entity_type>:<id>` を守る

#### 出力物
- `src/<module>.py` または単一ファイル実装

#### 完了条件
- [ ] 全テストが通過 (Green)
- [ ] 仕様書との整合性が取れている
- [ ] lint/type check が通る

---

### Phase 6: リファクタリング

#### 入力
- 動作するコード (Green)
- テストスイート

#### 手順
1. コードの重複を抽出
2. 関数・クラスの責務を整理
3. テストを実行 → 通過することを確認
4. 必要に応じてテストコードも整理

#### 注意点
- 機能追加は行わない
- パフォーマンス改善は別フェーズで検討
- テストが落ちたら即座に戻す

#### 完了条件
- [ ] テストが全て通過している
- [ ] コードカバレッジが維持/向上している
- [ ] 複雑度が低下している（任意）

---

### Phase 7: 受入確認

#### 入力
- 全テスト通過済みのコード
- MVP Spec

#### 手順
1. MVP Spec の「受け入れ条件」セクションを確認
2. 各条件について、対応するテストの存在を確認
3. エンドツーエンドで手動確認（オプション）
4. ドキュメント更新（CHANGELOG 等）

#### 受入チェックリスト（agent-taskstate MVP例）

- [ ] task を作成できる
- [ ] task_state を作成・更新できる
- [ ] decision を追加し、accept / reject できる
- [ ] open question を追加し、answer / defer できる
- [ ] run を開始・終了できる
- [ ] context bundle を生成・参照できる
- [ ] 生成した context bundle を見て、人間または LLM が次の一手を出せる
- [ ] task 単位の JSON export ができる

---

## 4. 仕様書テンプレート

### 4.1 MVP Spec テンプレート

```markdown
# <Project> MVP 仕様書

## 1. 概要
（1段落で目的を説明）

## 2. 設計原則
### 2.1 <原則名>
- ...

## 3. MVP スコープ
### 3.1 含む
- ...

### 3.2 含まない
- ...

## 4. ドメインモデル
### 4.1 <Entity>
#### 必須属性
- `attr`: <type> - <説明>
- ...

## 5. 状態遷移仕様
### 5.1 Status
- `status_a`
- `status_b`

### 5.2 許可遷移
- `status_a -> status_b`

## 6. CLI 仕様
### 6.1 <command>
- `<cli> <command> --arg <value>`
- 出力: { ... }

## 7. エラーコード
| code | 説明 |
|-----|------|
| not_found | ... |

## 8. 受け入れ条件
- [ ] ...
```

### 4.2 Test Case テンプレート

```gherkin
Feature: <機能名>

  Background:
    Given 空のデータベース

  Scenario: <正常系シナリオ>
    Given <前提条件>
    When <操作>
    Then <期待結果>

  Scenario Outline: <パラメータ化シナリオ>
    Given <前提条件>
    When <操作> with <param>
    Then <期待結果>

    Examples:
      | param | expected |
      | value1 | result1 |
      | value2 | result2 |
```

---

## 5. 仕様書とテストのトレーサビリティ

### 5.1 マッピング表

| 仕様セクション | テストファイル | テスト関数 |
|--------------|--------------|-----------|
| 5.1 Task | `test_task.py` | `TestTask*` |
| 5.2 Task State | `test_state.py` | `TestState*` |
| 5.3 Decision | `test_decision.py` | `TestDecision*` |
| 7.2 許可遷移 | `test_transitions.py` | `TestTransitions*` |

### 5.2 コメント規約

テストコード内で仕様書への参照を明示：

```python
def test_task_create_requires_kind(self):
    """Spec 6.2: task create --kind is required"""
    # MVP Spec Section 7.4: ready遷移ガード - kindが設定済み
```

---

## 6. 変更管理

### 6.1 仕様変更フロー

```
仕様変更要求
    ↓
影響範囲分析
    ↓
仕様書更新 → レビュー
    ↓
テストケース更新 → レビュー
    ↓
テスト実行 (Red になることを確認)
    ↓
実装修正
    ↓
テスト通過 (Green)
    ↓
CHANGELOG 更新
```

### 6.2 バージョン管理

- 仕様書の変更はコミットメッセージに `spec:` プレフィックス
- テスト追加は `test:` プレフィックス
- 実装は `feat:` / `fix:` プレフィックス

---

## 7. ツールチェーン

### 7.1 推奨ツール

| カテゴリ | ツール | 用途 |
|---------|-------|------|
| テストフレームワーク | pytest | 単体・統合テスト |
| テストカバレッジ | pytest-cov | カバレッジ計測 |
| 型チェック | mypy | 静的型検査 |
| Lint | ruff / flake8 | コード品質 |
| フォーマット | black | コード整形 |
| BDD | pytest-bdd | Gherkin形式テスト |

### 7.2 実行コマンド

```bash
# テスト実行
pytest tests/ -v

# カバレッジ付き
pytest tests/ --cov=src --cov-report=term-missing

# 型チェック
mypy src/

# Lint
ruff check src/ tests/

# フォーマット
black src/ tests/
```

---

## 8. チェックリスト

### フェーズ完了チェック

#### Phase 1: 要件分析
- [ ] 目的が明確
- [ ] スコープが明確
- [ ] コア概念が整理済み

#### Phase 2: 仕様策定
- [ ] 全エンティティ定義済み
- [ ] 状態遷移定義済み
- [ ] CLIコマンド定義済み
- [ ] エラーコード定義済み

#### Phase 3: テスト設計
- [ ] Happy Path テストあり
- [ ] 異常系テストあり
- [ ] ガード条件テストあり

#### Phase 4: テスト実装
- [ ] 全テストが Red 状態

#### Phase 5: 実装
- [ ] 全テストが Green 状態

#### Phase 6: リファクタリング
- [ ] テスト通過維持
- [ ] コード品質向上

#### Phase 7: 受入確認
- [ ] 受け入れ条件全項目クリア

---

## 9. 優先ロードマップ

実装の優先順位と依存関係は以下のロードマップに従うこと。

### 参照ファイル

**最重要**: `docs/kv-priority-roadmap/プライオリティ.md`

### 実施順序

| 優先度 | ファイル | 内容 |
|-------|---------|------|
| P1 | `kv-cache-independence-amendments.md` | KV-Cache独立性修正 |
| P2 | `01-typed-ref-unification.md` | typed_ref統一 |
| P3 | `02-workx-state-history-and-bundle-audit.md` | 状態履歴・バンドル監査 |
| P4 | `03-workx-memx-context-rebuild-resolver.md` | コンテキスト再構築リゾルバ |
| P5 | `04-tracker-bridge-minimum-integration.md` | Tracker-Bridge最小統合 |

### 注意事項

- **実施順を崩さないこと**: P1 → P2 → P3 → P4 の順序で進める
- **typed_ref統一前の並行開発は危険**: 各PJを並行で深く進める前に、必ずtyped_ref統一を完了させること