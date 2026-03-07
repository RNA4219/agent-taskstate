Feature: Task State Management
  Task State の作成・取得・更新を管理する（Optimistic Lock 付き）

  Background:
    Given 空のデータベース

  # ============================================
  # state put - 作成
  # ============================================

  Scenario: 新規 Task State 作成
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate state put --task 01HATASK0000000000001 --file state.json:
      """
      {
        "current_step": "実装中",
        "constraints": ["制約1", "制約2"],
        "done_when": ["条件1", "条件2"],
        "current_summary": "現在の要約",
        "artifact_refs": [],
        "evidence_refs": [],
        "confidence": "medium",
        "context_policy": {"force_evidence": false}
      }
      """
    Then 出力は ok=true である
    And 作成された state の revision は 1 である
    And 作成された state の current_step は "実装中" である
    And 作成された state の confidence は "medium" である

  Scenario: state put で既存を上書き
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | revision | current_step |
      | 01HATASK0000000000001 | 5        | 古い状態     |
    When agent-taskstate state put --task 01HATASK0000000000001 --file state.json:
      """
      {
        "current_step": "新しい状態",
        "constraints": [],
        "done_when": ["条件1"],
        "current_summary": "",
        "artifact_refs": [],
        "evidence_refs": [],
        "confidence": "high",
        "context_policy": {}
      }
      """
    Then 出力は ok=true である
    And state の revision は 1 にリセットされている
    And state の current_step は "新しい状態" である

  Scenario: 存在しない task で state put
    Given 空のデータベース
    When agent-taskstate state put --task 01HANOTFOUND000000000001 --file state.json
    Then 出力は error.code="not_found" である

  # ============================================
  # state get - 取得
  # ============================================

  Scenario: Task State 取得
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | revision | current_step | confidence |
      | 01HATASK0000000000001 | 3        | レビュー中   | high       |
    When agent-taskstate state get --task 01HATASK0000000000001
    Then 出力は ok=true である
    And 出力の data.revision は 3 である
    And 出力の data.current_step は "レビュー中" である
    And 出力の data.confidence は "high" である

  Scenario: Task State 未作成で not_found
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate state get --task 01HATASK0000000000001
    Then 出力は error.code="not_found" である

  Scenario: 存在しない task で state get
    Given 空のデータベース
    When agent-taskstate state get --task 01HANOTFOUND000000000001
    Then 出力は error.code="not_found" である

  # ============================================
  # state patch - 更新（Optimistic Lock）
  # ============================================

  Scenario: revision 一致で更新成功
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | revision | current_step |
      | 01HATASK0000000000001 | 1        | 実装前       |
    When agent-taskstate state patch --task 01HATASK0000000000001 --expected-revision 1 --file patch.json:
      """
      {
        "current_step": "実装中"
      }
      """
    Then 出力は ok=true である
    And state の revision は 2 である
    And state の current_step は "実装中" である

  Scenario: revision 不一致で conflict
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | revision | current_step |
      | 01HATASK0000000000001 | 5        | 最新状態     |
    When agent-taskstate state patch --task 01HATASK0000000000001 --expected-revision 3 --file patch.json:
      """
      {
        "current_step": "古い情報で更新"
      }
      """
    Then 出力は error.code="conflict" である
    And state は更新されていない（revision は 5 のまま）

  Scenario: 複数フィールド同時更新
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | revision | current_step | confidence |
      | 01HATASK0000000000001 | 2        | 実装中       | medium     |
    When agent-taskstate state patch --task 01HATASK0000000000001 --expected-revision 2 --file patch.json:
      """
      {
        "current_step": "レビュー中",
        "confidence": "high",
        "current_summary": "実装完了"
      }
      """
    Then 出力は ok=true である
    And state の revision は 3 である
    And state の current_step は "レビュー中" である
    And state の confidence は "high" である
    And state の current_summary は "実装完了" である

  Scenario: 存在しない task で state patch
    Given 空のデータベース
    When agent-taskstate state patch --task 01HANOTFOUND000000000001 --expected-revision 1 --file patch.json
    Then 出力は error.code="not_found" である

  Scenario: 存在しない state で state patch
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate state patch --task 01HATASK0000000000001 --expected-revision 1 --file patch.json
    Then 出力は error.code="not_found" である

  # ============================================
  # 競合シナリオ
  # ============================================

  Scenario: 並行更新の競合
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | revision |
      | 01HATASK0000000000001 | 1        |
    When プロセスA が state patch --expected-revision 1 で更新
    And プロセスB が state patch --expected-revision 1 で更新
    Then プロセスA は成功する
    And プロセスB は conflict になる
    And state の revision は 2 である

  # ============================================
  # バリデーション
  # ============================================

  Scenario: 不正な confidence で validation_error
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate state put --task 01HATASK0000000000001 --file state.json:
      """
      {
        "current_step": "test",
        "constraints": [],
        "done_when": [],
        "confidence": "invalid",
        "context_policy": {}
      }
      """
    Then 出力は error.code="validation_error" である

  Scenario Outline: 各 confidence で作成
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate state put --task 01HATASK0000000000001 --file state.json:
      """
      {
        "current_step": "test",
        "constraints": [],
        "done_when": [],
        "confidence": "<confidence>",
        "context_policy": {}
      }
      """
    Then 出力は ok=true である
    And state の confidence は "<confidence>" である

    Examples:
      | confidence |
      | low        |
      | medium     |
      | high       |