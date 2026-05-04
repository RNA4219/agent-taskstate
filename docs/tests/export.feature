Feature: Export Functionality
  Task 単位の JSON エクスポートを管理する

  Background:
    Given 空のデータベース

  # ============================================
  # export task - 正常系
  # ============================================

  Scenario: Task 単位エクスポート
    Given task が存在する:
      | id                    | kind    | title   | status |
      | 01HATASK0000000000001 | feature | TestTask| done   |
    And task_state が存在する:
      | task_id               | revision | current_step |
      | 01HATASK0000000000001 | 3        | 完了         |
    And decision が存在する:
      | id                     | task_id               | summary    | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | Decision1  | accepted |
      | 01HADECISION0000000002 | 01HATASK0000000000001 | Decision2  | rejected |
    And open_question が存在する:
      | id                      | task_id               | question   | status  |
      | 01HAQUESTION00000000001 | 01HATASK0000000000001 | Question1  | answered|
    And run が存在する:
      | id               | task_id               | run_type | status    |
      | 01HARUN000000001 | 01HATASK0000000000001 | plan     | succeeded |
      | 01HARUN000000002 | 01HATASK0000000000001 | execute  | succeeded |
    And context_bundle が存在する:
      | id                      | task_id               |
      | 01HACONTEXT000000000001 | 01HATASK0000000000001 |
    When agent-taskstate export task --task 01HATASK0000000000001 --output export.json
    Then 出力は ok=true である
    And export.json が作成される
    And export.json には以下が含まれる:
      | task            |
      | task_state      |
      | decisions[]     |
      | open_questions[]|
      | runs[]          |
      | context_bundles[]|

  Scenario: 最小構成の Task エクスポート
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               |
      | 01HATASK0000000000001 |
    When agent-taskstate export task --task 01HATASK0000000000001 --output minimal.json
    Then 出力は ok=true である
    And minimal.json には task と task_state のみが含まれる
    And decisions[] は空配列である
    And open_questions[] は空配列である
    And runs[] は空配列である
    And context_bundles[] は空配列である

  Scenario: 存在しない task で export
    Given 空のデータベース
    When agent-taskstate export task --task 01HANOTFOUND000000000001 --output export.json
    Then 出力は error.code="not_found" である

  # ============================================
  # 出力形式
  # ============================================

  Scenario: JSON 形式で出力
    Given task が存在する:
      | id                    | kind    | title   | goal   | status | priority |
      | 01HATASK0000000000001 | feature | TestTask| Goal1  | done   | high     |
    And task_state が存在する:
      | task_id               |
      | 01HATASK0000000000001 |
    When agent-taskstate export task --task 01HATASK0000000000001 --output export.json
    Then export.json は有効な JSON 形式である
    And 以下の構造を持つ:
      """
      {
        "task": { ... },
        "task_state": { ... },
        "decisions": [...],
        "open_questions": [...],
        "runs": [...],
        "context_bundles": [...],
        "exported_at": "<ISO8601>"
      }
      """

  Scenario: typed_ref は元の形式を維持
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | artifact_refs                         | evidence_refs                         |
      | 01HATASK0000000000001 | ["agent-taskstate:artifact:01HAART001"]        | ["memx:evidence:01HEV001"]           |
    When agent-taskstate export task --task 01HATASK0000000000001 --output export.json
    Then export.json の artifact_refs は typed_ref 形式を維持している
    And export.json の evidence_refs は typed_ref 形式を維持している

  # ============================================
  # ファイル出力
  # ============================================

  Scenario: 既存ファイルへの上書き
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する
    And ファイル export.json が既に存在する
    When agent-taskstate export task --task 01HATASK0000000000001 --output export.json
    Then 出力は ok=true である
    And export.json は上書きされる

  Scenario: 出力先ディレクトリが存在しない場合は作成
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する
    When agent-taskstate export task --task 01HATASK0000000000001 --output subdir/export.json
    Then 出力は ok=true である
    And subdir/ ディレクトリが作成される
    And export.json が作成される

  # ============================================
  # 用途
  # ============================================

  Scenario: バックアップ用途
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する
    When agent-taskstate export task --task 01HATASK0000000000001 --output backup-2025-01-15.json
    Then バックアップファイルが作成される
    And ファイルには全データが含まれる

  Scenario: 監査用途
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And decision が存在する:
      | id                     | summary     | status   | confidence |
      | 01HADECISION0000000001 | Decision1   | accepted | high       |
    And run が存在する:
      | id               | run_type | status    | started_at          | ended_at            |
      | 01HARUN000000001 | execute  | succeeded | 2025-01-15T10:00:00Z| 2025-01-15T11:00:00Z|
    When agent-taskstate export task --task 01HATASK0000000000001 --output audit.json
    Then 監査に必要な情報が全て含まれる:
      | 意思決定履歴       |
      | 実行記録          |
      | タイムスタンプ    |

  # ============================================
  # エクスポート内容の検証
  # ============================================

  Scenario: task 全フィールドが含まれる
    Given task が存在する:
      | id                    | parent_task_id        | kind    | title  | goal  | status | priority | owner_type | owner_id  |
      | 01HATASK0000000000001 | 01HAPARENT00000000001 | feature | Title  | Goal  | done   | high     | agent      | agent-001 |
    And task_state が存在する
    When agent-taskstate export task --task 01HATASK0000000000001 --output export.json
    Then export.json の task に全フィールドが含まれる

  Scenario: task_state 全フィールドが含まれる
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And task_state が存在する:
      | task_id               | revision | current_step | constraints  | done_when    | current_summary | confidence |
      | 01HATASK0000000000001 | 5        | 完了         | ["制約1"]   | ["条件1"]   | 完了しました    | high       |
    When agent-taskstate export task --task 01HATASK0000000000001 --output export.json
    Then export.json の task_state に全フィールドが含まれる

  Scenario: 複数 decision が正しく含まれる
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And decision が存在する:
      | id                     | summary    | status   | confidence |
      | 01HADECISION0000000001 | Decision1  | accepted | high       |
      | 01HADECISION0000000002 | Decision2  | proposed | medium     |
      | 01HADECISION0000000003 | Decision3  | rejected | low        |
    And task_state が存在する
    When agent-taskstate export task --task 01HATASK0000000000001 --output export.json
    Then export.json の decisions に3件が含まれる

  Scenario: 複数 open_question が正しく含まれる
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    And open_question が存在する:
      | id                      | question   | priority | status  | answer     |
      | 01HAQUESTION00000000001 | Question1  | high     | answered| Answer1    |
      | 01HAQUESTION00000000002 | Question2  | medium   | open    |            |
    And task_state が存在する
    When agent-taskstate export task --task 01HATASK0000000000001 --output export.json
    Then export.json の open_questions に2件が含まれる