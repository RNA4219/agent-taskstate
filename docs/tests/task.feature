Feature: Task Management
  Task の作成・参照・更新・状態遷移を管理する

  Background:
    Given 空のデータベース

  # ============================================
  # task create - 正常系
  # ============================================

  Scenario: 必須フィールドのみで Task 作成
    Given 空のデータベース
    When agent-taskstate task create --kind feature --title "新機能" --goal "実装する" --priority high --owner-type agent --owner-id agent-001
    Then 出力は以下の形式である:
      """
      {"ok": true, "data": {"task_id": "<ulid>"}, "error": null}
      """
    And task テーブルに1件追加されている
    And 作成された task の status は "draft" である
    And 作成された task の kind は "feature" である
    And 作成された task の priority は "high" である

  Scenario: 全フィールド指定で Task 作成
    Given 空のデータベース
    When agent-taskstate task create --kind bugfix --title "バグ修正" --goal "修正する" --priority critical --owner-type human --owner-id user-001 --parent-task-id "01HARENT0000000000000000001"
    Then 出力は ok=true である
    And parent_task_id が設定されている

  Scenario Outline: 各 kind で Task 作成
    Given 空のデータベース
    When agent-taskstate task create --kind <kind> --title "Test" --goal "Goal" --priority medium --owner-type agent --owner-id agent-001
    Then 出力は ok=true である
    And 作成された task の kind は "<kind>" である

    Examples:
      | kind     |
      | bugfix   |
      | feature  |
      | research |

  Scenario Outline: 各 priority で Task 作成
    Given 空のデータベース
    When agent-taskstate task create --kind feature --title "Test" --goal "Goal" --priority <priority> --owner-type agent --owner-id agent-001
    Then 出力は ok=true である
    And 作成された task の priority は "<priority>" である

    Examples:
      | priority |
      | low      |
      | medium   |
      | high     |
      | critical |

  Scenario Outline: 各 owner_type で Task 作成
    Given 空のデータベース
    When agent-taskstate task create --kind feature --title "Test" --goal "Goal" --priority medium --owner-type <owner_type> --owner-id <owner_id>
    Then 出力は ok=true である
    And 作成された task の owner_type は "<owner_type>" である

    Examples:
      | owner_type | owner_id   |
      | human      | user-001   |
      | agent      | agent-001  |
      | system     | system-001 |

  # ============================================
  # task create - バリデーションエラー
  # ============================================

  Scenario: kind 未指定で validation_error
    Given 空のデータベース
    When agent-taskstate task create --title "Test" --goal "Goal" --priority high --owner-type agent --owner-id agent-001
    Then 出力は error.code="validation_error" である

  Scenario: 不正な kind で validation_error
    Given 空のデータベース
    When agent-taskstate task create --kind invalid --title "Test" --goal "Goal" --priority high --owner-type agent --owner-id agent-001
    Then 出力は error.code="validation_error" である

  Scenario: 不正な priority で validation_error
    Given 空のデータベース
    When agent-taskstate task create --kind feature --title "Test" --goal "Goal" --priority urgent --owner-type agent --owner-id agent-001
    Then 出力は error.code="validation_error" である

  Scenario: 不正な owner_type で validation_error
    Given 空のデータベース
    When agent-taskstate task create --kind feature --title "Test" --goal "Goal" --priority high --owner-type robot --owner-id robot-001
    Then 出力は error.code="validation_error" である

  Scenario: title 未指定で validation_error
    Given 空のデータベース
    When agent-taskstate task create --kind feature --goal "Goal" --priority high --owner-type agent --owner-id agent-001
    Then 出力は error.code="validation_error" である

  Scenario: goal 未指定で validation_error
    Given 空のデータベース
    When agent-taskstate task create --kind feature --title "Test" --priority high --owner-type agent --owner-id agent-001
    Then 出力は error.code="validation_error" である

  # ============================================
  # task show
  # ============================================

  Scenario: 存在する Task の詳細取得
    Given task が存在する:
      | id                    | kind    | title  | goal   | status | priority |
      | 01HATASK0000000000001 | feature | Test 1 | Goal 1 | draft  | high     |
    When agent-taskstate task show --task 01HATASK0000000000001
    Then 出力は ok=true である
    And 出力の data.id は "01HATASK0000000000001" である
    And 出力の data.title は "Test 1" である
    And 出力の data.status は "draft" である

  Scenario: 存在しない Task ID で not_found
    Given 空のデータベース
    When agent-taskstate task show --task 01HANOTFOUND000000000001
    Then 出力は error.code="not_found" である

  # ============================================
  # task list
  # ============================================

  Scenario: 全 Task 一覧取得
    Given 以下の task が存在する:
      | id                    | kind    | title  | status      |
      | 01HATASK0000000000001 | feature | Task 1 | draft       |
      | 01HATASK0000000000002 | bugfix  | Task 2 | in_progress |
      | 01HATASK0000000000003 | feature | Task 3 | done        |
    When agent-taskstate task list
    Then 出力は ok=true である
    And 出力の data に3件の task が含まれる

  Scenario: status でフィルタ
    Given 以下の task が存在する:
      | id                    | kind    | title  | status      |
      | 01HATASK0000000000001 | feature | Task 1 | draft       |
      | 01HATASK0000000000002 | bugfix  | Task 2 | in_progress |
      | 01HATASK0000000000003 | feature | Task 3 | done        |
    When agent-taskstate task list --status draft
    Then 出力は ok=true である
    And 出力の data に1件の task が含まれる
    And 出力の data[0].status は "draft" である

  Scenario: kind でフィルタ
    Given 以下の task が存在する:
      | id                    | kind    | title  | status      |
      | 01HATASK0000000000001 | feature | Task 1 | draft       |
      | 01HATASK0000000000002 | bugfix  | Task 2 | in_progress |
      | 01HATASK0000000000003 | feature | Task 3 | done        |
    When agent-taskstate task list --kind bugfix
    Then 出力は ok=true である
    And 出力の data に1件の task が含まれる
    And 出力の data[0].kind は "bugfix" である

  Scenario: owner-type でフィルタ
    Given 以下の task が存在する:
      | id                    | owner_type | owner_id   |
      | 01HATASK0000000000001 | human      | user-001   |
      | 01HATASK0000000000002 | agent      | agent-001  |
    When agent-taskstate task list --owner-type agent
    Then 出力は ok=true である
    And 出力の data に1件の task が含まれる
    And 出力の data[0].owner_type は "agent" である

  Scenario: 複合フィルタ
    Given 以下の task が存在する:
      | id                    | kind    | status      | owner_type |
      | 01HATASK0000000000001 | feature | draft       | agent      |
      | 01HATASK0000000000002 | feature | in_progress | agent      |
      | 01HATASK0000000000003 | bugfix  | draft       | agent      |
    When agent-taskstate task list --kind feature --status draft
    Then 出力は ok=true である
    And 出力の data に1件の task が含まれる
    And 出力の data[0].kind は "feature" である
    And 出力の data[0].status は "draft" である

  # ============================================
  # task update
  # ============================================

  Scenario: Task の title 更新
    Given task が存在する:
      | id                    | title  |
      | 01HATASK0000000000001 | Before |
    When agent-taskstate task update --task 01HATASK0000000000001 --title "After"
    Then 出力は ok=true である
    And task の title は "After" に更新されている

  Scenario: 複数フィールド同時更新
    Given task が存在する:
      | id                    | title  | goal    | priority |
      | 01HATASK0000000000001 | Before | OldGoal | low      |
    When agent-taskstate task update --task 01HATASK0000000000001 --title "After" --goal "NewGoal" --priority high
    Then 出力は ok=true である
    And task の title は "After" に更新されている
    And task の priority は "high" に更新されている

  Scenario: 存在しない Task の更新で not_found
    Given 空のデータベース
    When agent-taskstate task update --task 01HANOTFOUND000000000001 --title "New Title"
    Then 出力は error.code="not_found" である

  # ============================================
  # task set-status - 正常遷移
  # ============================================

  Scenario: draft -> ready 遷移
    Given task が存在する:
      | id                    | status | goal   | kind    |
      | 01HATASK0000000000001 | draft  | Goal 1 | feature |
    And task_state が存在する:
      | task_id               | done_when        |
      | 01HATASK0000000000001 | ["条件1", "条件2"] |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to ready
    Then 出力は ok=true である
    And task の status は "ready" に更新されている

  Scenario: ready -> in_progress 遷移
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | ready  |
    And task_state が存在する:
      | task_id               | current_step |
      | 01HATASK0000000000001 | 実装中       |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to in_progress
    Then 出力は ok=true である
    And task の status は "in_progress" に更新されている

  Scenario: in_progress -> blocked 遷移
    Given task が存在する:
      | id                    | status      |
      | 01HATASK0000000000001 | in_progress |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to blocked
    Then 出力は ok=true である
    And task の status は "blocked" に更新されている

  Scenario: blocked -> in_progress 遷移
    Given task が存在する:
      | id                    | status  |
      | 01HATASK0000000000001 | blocked |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to in_progress
    Then 出力は ok=true である
    And task の status は "in_progress" に更新されている

  Scenario: in_progress -> review 遷移
    Given task が存在する:
      | id                    | status      |
      | 01HATASK0000000000001 | in_progress |
    And decision が存在する:
      | id                     | task_id               | status   |
      | 01HADECISION0000000001 | 01HATASK0000000000001 | accepted |
    And high priority の open question が存在しない
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to review
    Then 出力は ok=true である
    And task の status は "review" に更新されている

  Scenario: review -> done 遷移
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | review |
    And task_state が存在する:
      | task_id               | done_when      | current_summary |
      | 01HATASK0000000000001 | ["完了条件1"] | 完了しました   |
    And 過去に review 状態を通過している
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to done
    Then 出力は ok=true である
    And task の status は "done" に更新されている

  Scenario: done -> archived 遷移
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | done   |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to archived
    Then 出力は ok=true である
    And task の status は "archived" に更新されている

  # ============================================
  # task set-status - 例外遷移
  # ============================================

  Scenario: draft -> archived 例外遷移（理由あり）
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | draft  |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to archived --reason "不要になったため"
    Then 出力は ok=true である
    And task の status は "archived" に更新されている

  Scenario: draft -> archived 例外遷移（理由なし）
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | draft  |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to archived
    Then 出力は error.code="invalid_transition" である

  Scenario: done -> in_progress 例外遷移（理由あり）
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | done   |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to in_progress --reason "追加修正が発生"
    Then 出力は ok=true である
    And task の status は "in_progress" に更新されている

  # ============================================
  # task set-status - ガード条件違反
  # ============================================

  Scenario: ready 遷移 - goal が空
    Given task が存在する:
      | id                    | status | goal | kind    |
      | 01HATASK0000000000001 | draft  |      | feature |
    And task_state が存在する:
      | task_id               | done_when   |
      | 01HATASK0000000000001 | ["条件1"]   |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to ready
    Then 出力は error.code="invalid_transition" である

  Scenario: ready 遷移 - done_when が空
    Given task が存在する:
      | id                    | status | goal   | kind    |
      | 01HATASK0000000000001 | draft  | Goal 1 | feature |
    And task_state が存在する:
      | task_id               | done_when |
      | 01HATASK0000000000001 | []        |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to ready
    Then 出力は error.code="invalid_transition" である

  Scenario: in_progress 遷移 - task_state が存在しない
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | ready  |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to in_progress
    Then 出力は error.code="invalid_transition" である

  Scenario: in_progress 遷移 - current_step が空
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | ready  |
    And task_state が存在する:
      | task_id               | current_step |
      | 01HATASK0000000000001 |              |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to in_progress
    Then 出力は error.code="invalid_transition" である

  Scenario: review 遷移 - high priority の open question がある
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

  Scenario: review 遷移 - accepted/proposed の decision がない
    Given task が存在する:
      | id                    | status      |
      | 01HATASK0000000000001 | in_progress |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to review
    Then 出力は error.code="invalid_transition" である

  # ============================================
  # task set-status - 許可されていない遷移
  # ============================================

  Scenario: 許可されていない遷移 draft -> in_progress
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | draft  |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to in_progress
    Then 出力は error.code="invalid_transition" である

  Scenario: 許可されていない遷移 draft -> done
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | draft  |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to done
    Then 出力は error.code="invalid_transition" である

  Scenario: 許可されていない遷移 ready -> done
    Given task が存在する:
      | id                    | status |
      | 01HATASK0000000000001 | ready  |
    When agent-taskstate task set-status --task 01HATASK0000000000001 --to done
    Then 出力は error.code="invalid_transition" である