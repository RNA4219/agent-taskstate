Feature: Decision Management
  Decision の追加・一覧・承認・拒否を管理する

  Background:
    Given 空のデータベース

  # ============================================
  # decision add - 追加
  # ============================================

  Scenario: Decision 追加
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate decision add --task 01HATASK0000000000001 --file decision.json:
      """
      {
        "summary": "DB に SQLite を採用",
        "rationale": "ローカル実行で軽量なため",
        "confidence": "high",
        "evidence_refs": ["memx:evidence:01HEV001"]
      }
      """
    Then 出力は ok=true である
    And decision_id が返る
    And 作成された decision の status は "proposed" である
    And 作成された decision の confidence は "high" である

  Scenario: 最小フィールドで Decision 追加
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate decision add --task 01HATASK0000000000001 --file decision.json:
      """
      {
        "summary": "シンプルな決定",
        "confidence": "medium"
      }
      """
    Then 出力は ok=true である
    And 作成された decision の status は "proposed" である

  Scenario: 存在しない task で decision add
    Given 空のデータベース
    When agent-taskstate decision add --task 01HANOTFOUND000000000001 --file decision.json
    Then 出力は error.code="not_found" である

  Scenario: summary 未指定で validation_error
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate decision add --task 01HATASK0000000000001 --file decision.json:
      """
      {
        "confidence": "high"
      }
      """
    Then 出力は error.code="validation_error" である

  Scenario Outline: 各 confidence で Decision 追加
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate decision add --task 01HATASK0000000000001 --file decision.json:
      """
      {
        "summary": "test decision",
        "confidence": "<confidence>"
      }
      """
    Then 出力は ok=true である

    Examples:
      | confidence |
      | low        |
      | medium     |
      | high       |

  # ============================================
  # decision list - 一覧
  # ============================================

  Scenario: Task 配下の Decision 一覧
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And decision が存在する:
      | id                     | task_id               | summary    | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | Decision 1 | accepted |
      | 01HADECISION0000000002 | 01HATASK0000000000001 | Decision 2 | proposed |
      | 01HADECISION0000000003 | 01HATASK0000000000001 | Decision 3 | rejected |
    When agent-taskstate decision list --task 01HATASK0000000000001
    Then 出力は ok=true である
    And 出力の data に3件の decision が含まれる

  Scenario: status でフィルタ
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And decision が存在する:
      | id                     | task_id               | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | accepted |
      | 01HADECISION0000000002 | 01HATASK0000000000001 | proposed |
      | 01HADECISION0000000003 | 01HATASK0000000000001 | rejected |
    When agent-taskstate decision list --task 01HATASK0000000000001 --status accepted
    Then 出力は ok=true である
    And 出力の data に1件の decision が含まれる
    And 出力の data[0].status は "accepted" である

  Scenario: 複数 status でフィルタ
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And decision が存在する:
      | id                     | task_id               | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | accepted |
      | 01HADECISION0000000002 | 01HATASK0000000000001 | proposed |
      | 01HADECISION0000000003 | 01HATASK0000000000001 | rejected |
    When agent-taskstate decision list --task 01HATASK0000000000001 --status accepted --status proposed
    Then 出力は ok=true である
    And 出力の data に2件の decision が含まれる

  Scenario: Decision なし
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate decision list --task 01HATASK0000000000001
    Then 出力は ok=true である
    And 出力の data は空の配列である

  # ============================================
  # decision accept - 承認
  # ============================================

  Scenario: Decision 承認
    Given decision が存在する:
      | id                     | status   |
      | 01HADECISION0000000001 | proposed |
    When agent-taskstate decision accept --decision 01HADECISION0000000001
    Then 出力は ok=true である
    And decision の status は "accepted" になる

  Scenario: 既に accepted の Decision は冪等
    Given decision が存在する:
      | id                     | status   |
      | 01HADECISION0000000001 | accepted |
    When agent-taskstate decision accept --decision 01HADECISION0000000001
    Then 出力は ok=true である
    And decision の status は "accepted" のままである

  Scenario: rejected の Decision を accept
    Given decision が存在する:
      | id                     | status   |
      | 01HADECISION0000000001 | rejected |
    When agent-taskstate decision accept --decision 01HADECISION0000000001
    Then 出力は ok=true である
    And decision の status は "accepted" になる

  Scenario: 存在しない decision で accept
    Given 空のデータベース
    When agent-taskstate decision accept --decision 01HANOTFOUND00000000001
    Then 出力は error.code="not_found" である

  # ============================================
  # decision reject - 拒否
  # ============================================

  Scenario: Decision 拒否
    Given decision が存在する:
      | id                     | status   |
      | 01HADECISION0000000001 | proposed |
    When agent-taskstate decision reject --decision 01HADECISION0000000001
    Then 出力は ok=true である
    And decision の status は "rejected" になる

  Scenario: 既に rejected の Decision は冪等
    Given decision が存在する:
      | id                     | status   |
      | 01HADECISION0000000001 | rejected |
    When agent-taskstate decision reject --decision 01HADECISION0000000001
    Then 出力は ok=true である
    And decision の status は "rejected" のままである

  Scenario: accepted の Decision を reject
    Given decision が存在する:
      | id                     | status   |
      | 01HADECISION0000000001 | accepted |
    When agent-taskstate decision reject --decision 01HADECISION0000000001
    Then 出力は ok=true である
    And decision の status は "rejected" になる

  Scenario: 存在しない decision で reject
    Given 空のデータベース
    When agent-taskstate decision reject --decision 01HANOTFOUND00000000001
    Then 出力は error.code="not_found" である

  # ============================================
  # supersedes 連鎖
  # ============================================

  Scenario: Decision の置き換え
    Given decision が存在する:
      | id                     | task_id               | summary     | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | Old Decision| accepted |
    When agent-taskstate decision add --task 01HATASK0000000000001 --file decision.json:
      """
      {
        "summary": "New Decision",
        "confidence": "high",
        "supersedes_decision_id": "01HADECISION0000000001"
      }
      """
    Then 新しい decision が作成される
    And 古い decision の status は "superseded" になる