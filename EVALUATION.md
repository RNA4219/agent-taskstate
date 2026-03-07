# agent-taskstate Evaluation Criteria

本ドキュメントは agent-taskstate MVP の受入基準と評価観点を定義する。

---

## 1. Acceptance Criteria（受入基準）

### 1.1 Core Features

以下の機能が全て動作することを MVP 受入の必須条件とする。

| ID | 機能 | 受入基準 | 対応仕様 |
|----|------|---------|---------|
| AC-001 | Task 作成 | 必須フィールド指定で task を作成し、`ok=true` と `task_id` が返る | Spec 5.1, 10.2 |
| AC-002 | Task 一覧 | `task list` で status/kind/owner でフィルタ可能 | Spec 10.2 |
| AC-003 | Task 状態遷移 | 許可された遷移のみ可能。ガード条件違反は `invalid_transition` | Spec 7.2-7.4 |
| AC-004 | Task State 取得 | `state get` で現在の revision 含む状態を取得 | Spec 5.2, 10.2 |
| AC-005 | Task State 更新 | `state patch` で optimistic lock 付き更新。不整合は `conflict` | Spec 5.2, 12 |
| AC-006 | Decision 追加 | decision を追加し、accept/reject で状態変更可能 | Spec 5.3, 10.2 |
| AC-007 | Open Question 追加 | question を追加し、answer/defer で状態変更可能 | Spec 5.4, 10.2 |
| AC-008 | Run 記録 | run start/finish で実行記録を残せる | Spec 5.5, 10.2 |
| AC-009 | Context Bundle 生成 | `context build` で必要な情報を束ねた bundle を生成 | Spec 5.6, 8, 10.2 |
| AC-010 | JSON Export | task 単位で全関連データを JSON export 可能 | Spec 14 |

### 1.2 Quality Gates

| ID | 観点 | 基準 | 検証方法 |
|----|------|------|---------|
| QG-001 | JSON 契約 | 全コマンドが `{ok, data, error}` 形式を出力 | 結合テスト |
| QG-002 | エラーコード | 定義された5種類のエラーコードのみ返却 | 異常系テスト |
| QG-003 | typed_ref 形式 | 全参照が `<namespace>:<entity_type>:<id>` 形式 | 単体テスト |
| QG-004 | 楽観ロック | `state patch` の競合で `conflict` 返却 | 並行テスト |
| QG-005 | 性能 | 主要操作が体感1秒未満 | 手動確認 |

---

## 2. Test Scenarios

### 2.1 Task Management

#### TC-TASK-001: Task 作成（正常系）

```gherkin
Scenario: 必須フィールドで Task 作成
  Given 空のデータベース
  When agent-taskstate task create --kind feature --title "Test Task" --goal "Test goal" --priority high --owner-type agent --owner-id agent-001
  Then 出力は {"ok": true, "data": {"task_id": "<ulid>"}, "error": null}
  And task テーブルに1件追加されている
  And status は "draft" である
```

#### TC-TASK-002: Task 作成（バリデーションエラー）

```gherkin
Scenario: kind 未指定で validation_error
  Given 空のデータベース
  When agent-taskstate task create --title "Test" --goal "Goal" --priority high --owner-type agent --owner-id agent-001
  Then 出力は {"ok": false, "data": null, "error": {"code": "validation_error", "message": "..."}}
```

#### TC-TASK-003: Task 状態遷移（正常）

```gherkin
Scenario: draft -> ready -> in_progress
  Given task が存在 (status=draft, goal="...", done_when=["条件1"])
  And kind が設定済み
  When agent-taskstate task set-status --task <id> --to ready
  Then status が "ready" になる
  When agent-taskstate task set-status --task <id> --to in_progress
  Then status が "in_progress" になる
```

#### TC-TASK-004: Task 状態遷移（ガード違反）

```gherkin
Scenario: goal 未設定で ready 遷移不可
  Given task が存在 (status=draft, goal="")
  When agent-taskstate task set-status --task <id> --to ready
  Then 出力は {"ok": false, "data": null, "error": {"code": "invalid_transition", "message": "..."}}
```

### 2.2 Task State

#### TC-STATE-001: State 作成・取得

```gherkin
Scenario: Task State 作成と取得
  Given task が存在
  When agent-taskstate state put --task <id> --file state.json
  Then state が作成され、revision=1 である
  When agent-taskstate state get --task <id>
  Then revision=1 の state が返る
```

#### TC-STATE-002: Optimistic Lock 成功

```gherkin
Scenario: revision 一致で更新成功
  Given task_state が存在 (revision=1)
  When agent-taskstate state patch --task <id> --file patch.json --expected-revision 1
  Then state が更新され、revision=2 になる
```

#### TC-STATE-003: Optimistic Lock 競合

```gherkin
Scenario: revision 不一致で conflict
  Given task_state が存在 (revision=2)
  When agent-taskstate state patch --task <id> --file patch.json --expected-revision 1
  Then 出力は {"ok": false, "data": null, "error": {"code": "conflict", "message": "..."}}
```

### 2.3 Decision

#### TC-DECISION-001: Decision 追加・承認

```gherkin
Scenario: Decision 追加と accept
  Given task が存在
  When agent-taskstate decision add --task <id> --file decision.json
  Then decision が status="proposed" で作成される
  When agent-taskstate decision accept --decision <decision_id>
  Then decision の status が "accepted" になる
```

#### TC-DECISION-002: Decision 拒否

```gherkin
Scenario: Decision reject
  Given decision が存在 (status=proposed)
  When agent-taskstate decision reject --decision <id>
  Then decision の status が "rejected" になる
```

### 2.4 Open Question

#### TC-QUESTION-001: Question 追加・回答

```gherkin
Scenario: Question 追加と answer
  Given task が存在
  When agent-taskstate question add --task <id> --file question.json
  Then question が status="open" で作成される
  When agent-taskstate question answer --question <id> --answer "回答内容"
  Then question の status が "answered" になり、answer が設定される
```

#### TC-QUESTION-002: high priority 問題による review 遷移ブロック

```gherkin
Scenario: high priority の open question があると review 不可
  Given task が存在 (status=in_progress)
  And open question が存在 (priority=high, status=open)
  When agent-taskstate task set-status --task <id> --to review
  Then 出力は {"ok": false, "data": null, "error": {"code": "invalid_transition", "message": "..."}}
```

### 2.5 Run

#### TC-RUN-001: Run 開始・終了

```gherkin
Scenario: Run start と finish
  Given task が存在
  When agent-taskstate run start --task <id> --run-type execute --actor-type agent --actor-id agent-001
  Then run が status="running" で作成される
  And run_id が返る
  When agent-taskstate run finish --run <run_id> --status succeeded --output-ref "agent-taskstate:artifact:xxx"
  Then run の status が "succeeded" になり、ended_at が設定される
```

### 2.6 Context Bundle

#### TC-CONTEXT-001: Context Bundle 生成

```gherkin
Scenario: Context Bundle 正常生成
  Given task が存在 (status=in_progress)
  And task_state が存在
  And decision が存在 (status=accepted)
  And open question が存在 (status=open)
  When agent-taskstate context build --task <id> --reason normal
  Then bundle が作成される
  And bundle には以下が含まれる:
    | task 基本情報 |
    | 最新 task_state |
    | accepted decisions |
    | open な open_questions |
```

#### TC-CONTEXT-002: Evidence 含有条件

```gherkin
Scenario: confidence=low の時に evidence を含める
  Given task が存在
  And task_state.confidence = "low"
  And evidence_refs が設定されている
  When agent-taskstate context build --task <id> --reason normal
  Then bundle.included_evidence_refs が空でない
```

### 2.7 Export

#### TC-EXPORT-001: Task 単位エクスポート

```gherkin
Scenario: Task 全データの JSON エクスポート
  Given task が存在
  And task_state が存在
  And decision が2件存在
  And open_question が1件存在
  And run が1件存在
  When agent-taskstate export task --task <id> --output export.json
  Then export.json には以下が含まれる:
    | task |
    | task_state |
    | decisions[] |
    | open_questions[] |
    | runs[] |
    | context_bundles[] |
```

---

## 3. Validation Matrix

### 3.1 状態遷移ガード条件

| 遷移 | ガード条件 | エラーコード |
|-----|-----------|------------|
| -> ready | goal ≠ empty, done_when ≥ 1, kind 設定済み | invalid_transition |
| -> in_progress | task_state 存在, current_step ≠ empty | invalid_transition |
| -> review | high priority open question = 0, (accepted or proposed) decision ≥ 1 | invalid_transition |
| -> done | done_when 全満足, current_summary 存在, review 通過済み | invalid_transition |

### 3.2 必須フィールド

| エンティティ | 必須フィールド |
|------------|---------------|
| Task | id, kind, title, goal, status, priority, owner_type, owner_id |
| Task State | task_id, revision, current_step, constraints, done_when, confidence |
| Decision | id, task_id, summary, status, confidence |
| Open Question | id, task_id, question, priority, status |
| Run | id, task_id, actor_type, actor_id, run_type, status |
| Context Bundle | id, task_id, build_reason, state_snapshot |

### 3.3 列挙値

| フィールド | 許容値 |
|-----------|-------|
| Task.kind | bugfix, feature, research |
| Task.status | draft, ready, in_progress, blocked, review, done, archived |
| Task.priority | low, medium, high, critical |
| Task.owner_type | human, agent, system |
| Decision.status | proposed, accepted, rejected, superseded |
| Decision.confidence | low, medium, high |
| Question.status | open, answered, deferred, invalid |
| Question.priority | low, medium, high |
| Run.status | running, succeeded, failed, cancelled |
| Run.run_type | plan, execute, review, summarize, sync, manual |
| Context Bundle.build_reason | normal, ambiguity, review, high_risk, recovery |
| Task State.confidence | low, medium, high |

---

## 4. Error Code Specification

| Code | 発生条件 | HTTP Status (将来的なAPI用) |
|------|---------|---------------------------|
| not_found | 指定された ID のエンティティが存在しない | 404 |
| validation_error | 必須フィールド欠落、型不正、列挙値不正 | 400 |
| invalid_transition | 状態遷移ガード違反 | 400 |
| conflict | revision 不一致（optimistic lock） | 409 |
| dependency_blocked | 外部依存の解決不可（将来用） | 424 |

---

## 5. Performance Criteria

| 操作 | 基準 | 測定方法 |
|-----|------|---------|
| task create | 1秒未満 | 手動実行 |
| task list (100件) | 1秒未満 | 手動実行 |
| state get | 1秒未満 | 手動実行 |
| state patch | 1秒未満 | 手動実行 |
| context build | 1秒未満（外部参照なし） | 手動実行 |
| export task | 数秒以内 | 手動実行 |

---

## 6. Non-Functional Requirements

### 6.1 運用要件

| ID | 要件 | 基準 |
|----|------|------|
| NFR-001 | オフライン動作 | ネットワーク接続不要で全機能利用可能 |
| NFR-002 | 単一ユーザー | 同時アクセス制御なし（optimistic lock のみ） |
| NFR-003 | データ可搬性 | JSON export で全データ抽出可能 |
| NFR-004 | データ整合性 | SQLite FK 制約による整合性保証 |

### 6.2 セキュリティ要件

| ID | 要件 | 基準 |
|----|------|------|
| SEC-001 | ローカル実行 | 外部通信なし |
| SEC-002 | 認証なし | 単一ユーザー前提で認証不要 |
| SEC-003 | データ保護 | DB ファイルはユーザーホーム配下に配置 |

---

## 7. Sign-Off Checklist

MVP リリース前に以下を全て確認すること。

### 機能確認

- [ ] AC-001 ~ AC-010 の全ての受入基準を満たしている
- [ ] TC-xxx の全テストシナリオが通過している
- [ ] エラーコードが5種類のみ返却されている

### 品質確認

- [ ] 全コマンドが JSON 契約を守っている
- [ ] typed_ref 形式が全ての参照で使用されている
- [ ] 楽観ロックが正しく動作している
- [ ] 性能基準を満たしている

### ドキュメント確認

- [ ] MVP Spec と実装が整合している
- [ ] CHANGELOG に記録されている
- [ ] CLI --help が全コマンドで動作する

---

## 8. Test Coverage Target

| カテゴリ | 目標カバレッジ |
|---------|---------------|
| 正常系 (Happy Path) | 100% |
| 異常系 (Error Cases) | 100% |
| ガード条件 | 100% |
| 境界値 | 80%以上 |

---

## 9. Evaluation Process

### 9.1 継続的評価

各コミット/PRで以下を自動実行：

```bash
# テスト実行
pytest tests/ -v --cov=src --cov-report=term-missing

# 型チェック
mypy src/

# Lint
ruff check src/ tests/
```

### 9.2 リリース判定

1. 全テスト通過
2. カバレッジ目標達成
3. 受入基準チェックリスト完了
4. ドキュメント整合性確認