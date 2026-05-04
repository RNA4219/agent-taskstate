Feature: Context Bundle Management
  Context Bundle の生成・参照を管理する

  Background:
    Given 空のデータベース

  # ============================================
  # context build - 生成
  # ============================================

  Scenario: Context Bundle 生成（正常）
    Given task が存在する:
      | id                    | kind    | title    | goal      | status      |
      | 01HATASK0000000000001 | feature | Feature1 | Implement | in_progress |
    And task_state が存在する:
      | task_id               | revision | current_step | confidence |
      | 01HATASK0000000000001 | 1        | 実装中       | high       |
    And decision が存在する:
      | id                     | task_id               | summary        | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | SQLite採用     | accepted |
    And open_question が存在する:
      | id                      | task_id               | question        | status |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | パフォーマンス？ | open   |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason normal
    Then 出力は ok=true である
    And bundle_id が返る
    And bundle の build_reason は "normal" である

  Scenario: Context Bundle には常に含まれる情報
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | done_when       |
      | 01HATASK0000000000001 | ["条件1"]      |
    And decision が存在する:
      | id                     | task_id               | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | accepted |
    And open_question が存在する:
      | id                      | task_id               | status |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | open   |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason normal
    Then bundle には以下が含まれる:
      | task 基本情報        |
      | 最新 task_state      |
      | accepted decisions   |
      | open な open_questions |
      | done_when            |
      | current_step         |

  Scenario: proposed decision も含める
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する
    And decision が存在する:
      | id                     | status   |
      | 01HADECISION0000000001 | proposed |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason normal
    Then bundle に proposed decisions が含まれる

  Scenario: 存在しない task で context build
    Given 空のデータベース
    When agent-taskstate context build --task 01HANOTFOUND000000000001 --reason normal
    Then 出力は error.code="not_found" である

  Scenario Outline: 各 build_reason で生成
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する
    When agent-taskstate context build --task 01HATASK0000000000001 --reason <reason>
    Then 出力は ok=true である
    And bundle の build_reason は "<reason>" である

    Examples:
      | reason    |
      | normal    |
      | ambiguity |
      | review    |
      | high_risk |
      | recovery  |

  Scenario: 不正な build_reason で validation_error
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する
    When agent-taskstate context build --task 01HATASK0000000000001 --reason invalid
    Then 出力は error.code="validation_error" である

  # ============================================
  # Evidence 含有条件
  # ============================================

  Scenario: confidence=low の時に evidence を含める
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | confidence | evidence_refs                  |
      | 01HATASK0000000000001 | low        | ["memx:evidence:01HEV001"]    |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason normal
    Then bundle.included_evidence_refs は空でない

  Scenario: decision.confidence=low の時に evidence を含める
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | confidence |
      | 01HATASK0000000000001 | high       |
    And decision が存在する:
      | id                     | confidence | evidence_refs                  |
      | 01HADECISION0000000001 | low        | ["memx:evidence:01HEV002"]    |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason normal
    Then bundle.included_evidence_refs は空でない

  Scenario: build_reason=review の時に evidence を含める
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | confidence | evidence_refs                  |
      | 01HATASK0000000000001 | high       | ["memx:evidence:01HEV003"]    |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason review
    Then bundle.included_evidence_refs は空でない

  Scenario: high priority open question がある時に evidence を含める
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | confidence | evidence_refs                  |
      | 01HATASK0000000000001 | high       | ["memx:evidence:01HEV004"]    |
    And open_question が存在する:
      | id                      | priority | status |
      | 01HAQUESTION00000000001 | high     | open   |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason normal
    Then bundle.included_evidence_refs は空でない

  Scenario: context_policy.force_evidence=true の時に evidence を含める
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | confidence | context_policy              | evidence_refs                  |
      | 01HATASK0000000000001 | high       | {"force_evidence": true}    | ["memx:evidence:01HEV005"]    |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason normal
    Then bundle.included_evidence_refs は空でない

  Scenario: 条件を満たさない場合は evidence を含めない
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | confidence | context_policy              | evidence_refs |
      | 01HATASK0000000000001 | high       | {"force_evidence": false}   | []            |
    And decision が存在する:
      | id                     | confidence |
      | 01HADECISION0000000001 | high       |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason normal
    Then bundle.included_evidence_refs は空である

  # ============================================
  # context show - 参照
  # ============================================

  Scenario: Context Bundle 参照
    Given context_bundle が存在する:
      | id                      | task_id               | build_reason |
      | 01HACONTEXT000000000001 | 01HATASK0000000000001 | normal       |
    When agent-taskstate context show --bundle 01HACONTEXT000000000001
    Then 出力は ok=true である
    And 出力の data.id は "01HACONTEXT000000000001" である
    And 出力の data.build_reason は "normal" である

  Scenario: 存在しない bundle で not_found
    Given 空のデータベース
    When agent-taskstate context show --bundle 01HANOTFOUND000000000001
    Then 出力は error.code="not_found" である

  # ============================================
  # expected_output_schema
  # ============================================

  Scenario: expected_output_schema が含まれる
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する
    When agent-taskstate context build --task 01HATASK0000000000001 --reason normal
    Then bundle.expected_output_schema が含まれる
    And expected_output_schema は以下の形式である:
      """
      {
        "summary": "string",
        "proposed_actions": ["string"],
        "decision_candidates": ["string"],
        "question_candidates": ["string"],
        "evidence_needed": ["string"]
      }
      """

  # ============================================
  # typed_ref 形式
  # ============================================

  Scenario: included_refs が typed_ref 形式
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | artifact_refs                         | evidence_refs                         |
      | 01HATASK0000000000001 | ["agent-taskstate:artifact:01HAART001"]        | ["memx:evidence:01HEV001"]           |
    When agent-taskstate context build --task 01HATASK0000000000001 --reason review
    Then bundle.included_artifact_refs は typed_ref 形式である
    And bundle.included_evidence_refs は typed_ref 形式である

  # ============================================
  # Immutability
  # ============================================

  Scenario: Context Bundle は不変
    Given context_bundle が存在する:
      | id                      | state_snapshot       |
      | 01HACONTEXT000000000001 | {"old": "state"}     |
    When 同じ task で新しい bundle を生成
    Then 古い bundle は変更されない
    And 新しい bundle が作成される