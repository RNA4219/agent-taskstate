Feature: Open Question Management
  Open Question の追加・一覧・回答・延期を管理する

  Background:
    Given 空のデータベース

  # ============================================
  # question add - 追加
  # ============================================

  Scenario: Question 追加
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate question add --task 01HATASK0000000000001 --file question.json:
      """
      {
        "question": "どの DB を使用するか？",
        "priority": "high"
      }
      """
    Then 出力は ok=true である
    And question_id が返る
    And 作成された question の status は "open" である
    And 作成された question の priority は "high" である

  Scenario: evidence_refs 付きで Question 追加
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate question add --task 01HATASK0000000000001 --file question.json:
      """
      {
        "question": "パフォーマンス要件は？",
        "priority": "medium",
        "evidence_refs": ["memx:evidence:01HEV001"]
      }
      """
    Then 出力は ok=true である
    And 作成された question の evidence_refs が設定されている

  Scenario: 存在しない task で question add
    Given 空のデータベース
    When agent-taskstate question add --task 01HANOTFOUND000000000001 --file question.json
    Then 出力は error.code="not_found" である

  Scenario: question 未指定で validation_error
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate question add --task 01HATASK0000000000001 --file question.json:
      """
      {
        "priority": "high"
      }
      """
    Then 出力は error.code="validation_error" である

  Scenario Outline: 各 priority で Question 追加
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate question add --task 01HATASK0000000000001 --file question.json:
      """
      {
        "question": "test question",
        "priority": "<priority>"
      }
      """
    Then 出力は ok=true である

    Examples:
      | priority |
      | low      |
      | medium   |
      | high     |

  # ============================================
  # question list - 一覧
  # ============================================

  Scenario: Task 配下の Question 一覧
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And open_question が存在する:
      | id                      | task_id               | question     | status  |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | Question 1   | open    |
      | 01HAQUESTION00000000002 | 01HATASK0000000000001 | Question 2   | answered|
      | 01HAQUESTION00000000003 | 01HATASK0000000000001 | Question 3   | deferred|
    When agent-taskstate question list --task 01HATASK0000000000001
    Then 出力は ok=true である
    And 出力の data に3件の question が含まれる

  Scenario: status でフィルタ
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And open_question が存在する:
      | id                      | task_id               | status  |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | open    |
      | 01HAQUESTION00000000002 | 01HATASK0000000000001 | answered|
    When agent-taskstate question list --task 01HATASK0000000000001 --status open
    Then 出力は ok=true である
    And 出力の data に1件の question が含まれる
    And 出力の data[0].status は "open" である

  Scenario: priority でフィルタ
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And open_question が存在する:
      | id                      | task_id               | priority |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | high     |
      | 01HAQUESTION00000000002 | 01HATASK0000000000001 | low      |
    When agent-taskstate question list --task 01HATASK0000000000001 --priority high
    Then 出力は ok=true である
    And 出力の data に1件の question が含まれる
    And 出力の data[0].priority は "high" である

  Scenario: 複合フィルタ
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And open_question が存在する:
      | id                      | task_id               | status | priority |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | open   | high     |
      | 01HAQUESTION00000000002 | 01HATASK0000000000001 | open   | low      |
      | 01HAQUESTION00000000003 | 01HATASK0000000000001 | answered| high    |
    When agent-taskstate question list --task 01HATASK0000000000001 --status open --priority high
    Then 出力は ok=true である
    And 出力の data に1件の question が含まれる

  Scenario: Question なし
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate question list --task 01HATASK0000000000001
    Then 出力は ok=true である
    And 出力の data は空の配列である

  # ============================================
  # question answer - 回答
  # ============================================

  Scenario: Question 回答
    Given open_question が存在する:
      | id                      | status |
      | 01HAQUESTION00000000001 | open   |
    When agent-taskstate question answer --question 01HAQUESTION00000000001 --answer "SQLite を採用する"
    Then 出力は ok=true である
    And question の status は "answered" になる
    And question の answer は "SQLite を採用する" である

  Scenario: 既に answered の Question を再回答
    Given open_question が存在する:
      | id                      | status  | answer      |
      | 01HAQUESTION00000000001 | answered| Old Answer  |
    When agent-taskstate question answer --question 01HAQUESTION00000000001 --answer "New Answer"
    Then 出力は ok=true である
    And question の answer は "New Answer" に更新される

  Scenario: 存在しない question で answer
    Given 空のデータベース
    When agent-taskstate question answer --question 01HANOTFOUND00000000001 --answer "test"
    Then 出力は error.code="not_found" である

  Scenario: evidence_refs 付きで回答
    Given open_question が存在する:
      | id                      | status |
      | 01HAQUESTION00000000001 | open   |
    When agent-taskstate question answer --question 01HAQUESTION00000000001 --answer "決定事項" --evidence-refs '["memx:evidence:01HEV001"]'
    Then 出力は ok=true である
    And question の evidence_refs が更新される

  # ============================================
  # question defer - 延期
  # ============================================

  Scenario: Question 延期
    Given open_question が存在する:
      | id                      | status | priority |
      | 01HAQUESTION00000000001 | open   | high     |
    When agent-taskstate question defer --question 01HAQUESTION00000000001
    Then 出力は ok=true である
    And question の status は "deferred" になる

  Scenario: 延期理由付き
    Given open_question が存在する:
      | id                      | status |
      | 01HAQUESTION00000000001 | open   |
    When agent-taskstate question defer --question 01HAQUESTION00000000001 --reason "MVP後に対処"
    Then 出力は ok=true である
    And question の status は "deferred" になる
    And question に理由が記録される

  Scenario: 存在しない question で defer
    Given 空のデータベース
    When agent-taskstate question defer --question 01HANOTFOUND00000000001
    Then 出力は error.code="not_found" である

  # ============================================
  # review 遷移への影響
  # ============================================

  Scenario: high priority open question があると review 不可
    Given task が存在する:
      | id                    | status      |
      | 01HATASK0000000000001 | in_progress |
    And decision が存在する:
      | id                     | task_id               | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | accepted |
    And open_question が存在する:
      | id                      | task_id               | priority | status |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | high     | open   |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to review
    Then 出力は error.code="invalid_transition" である

  Scenario: high priority でも answered なら review 可能
    Given task が存在する:
      | id                    | status      |
      | 01HATASK0000000000001 | in_progress |
    And decision が存在する:
      | id                     | task_id               | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | accepted |
    And open_question が存在する:
      | id                      | task_id               | priority | status  |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | high     | answered|
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to review
    Then 出力は ok=true である

  Scenario: low priority open question があっても review 可能
    Given task が存在する:
      | id                    | status      |
      | 01HATASK0000000000001 | in_progress |
    And decision が存在する:
      | id                     | task_id               | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | accepted |
    And open_question が存在する:
      | id                      | task_id               | priority | status |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | low      | open   |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to review
    Then 出力は ok=true である

  # ============================================
  # 無効化
  # ============================================

  Scenario: Question の無効化（直接 status 変更なし）
    Given open_question が存在する:
      | id                      | status |
      | 01HAQUESTION00000000001 | open   |
    When 別の手段で status を "invalid" に設定
    Then question の status は "invalid" になる
    And review 遷移のブロック対象外になる