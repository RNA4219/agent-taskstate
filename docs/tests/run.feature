Feature: Run Management
  Run の開始・終了を記録する

  Background:
    Given 空のデータベース

  # ============================================
  # run start - 開始
  # ============================================

  Scenario: Run 開始
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate run start --task 01HATASK0000000000001 --run-type execute --actor-type agent --actor-id agent-001
    Then 出力は ok=true である
    And run_id が返る
    And 作成された run の status は "running" である
    And 作成された run の run_type は "execute" である
    And 作成された run の started_at が設定されている

  Scenario: input_ref 付きで Run 開始
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate run start --task 01HATASK0000000000001 --run-type plan --actor-type human --actor-id user-001 --input-ref "agent-taskstate:context_bundle:01HACONTEXT001"
    Then 出力は ok=true である
    And 作成された run の input_ref が設定されている

  Scenario: 存在しない task で run start
    Given 空のデータベース
    When agent-taskstate run start --task 01HANOTFOUND000000000001 --run-type execute --actor-type agent --actor-id agent-001
    Then 出力は error.code="not_found" である

  Scenario Outline: 各 run_type で Run 開始
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate run start --task 01HATASK0000000000001 --run-type <run_type> --actor-type agent --actor-id agent-001
    Then 出力は ok=true である

    Examples:
      | run_type  |
      | plan      |
      | execute   |
      | review    |
      | summarize |
      | sync      |
      | manual    |

  Scenario Outline: 各 actor_type で Run 開始
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate run start --task 01HATASK0000000000001 --run-type execute --actor-type <actor_type> --actor-id <actor_id>
    Then 出力は ok=true である

    Examples:
      | actor_type | actor_id  |
      | human      | user-001  |
      | agent      | agent-001 |
      | system     | sys-001   |

  Scenario: 不正な run_type で validation_error
    Given task が存在する:
      | id                    |
      | 01HATASK0000000000001 |
    When agent-taskstate run start --task 01HATASK0000000000001 --run-type invalid --actor-type agent --actor-id agent-001
    Then 出力は error.code="validation_error" である

  # ============================================
  # run finish - 終了
  # ============================================

  Scenario: Run 正常終了
    Given run が存在する:
      | id               | status  |
      | 01HARUN000000001 | running |
    When agent-taskstate run finish --run 01HARUN000000001 --status succeeded
    Then 出力は ok=true である
    And run の status は "succeeded" になる
    And run の ended_at が設定されている

  Scenario: Run 失敗終了
    Given run が存在する:
      | id               | status  |
      | 01HARUN000000001 | running |
    When agent-taskstate run finish --run 01HARUN000000001 --status failed
    Then 出力は ok=true である
    And run の status は "failed" になる

  Scenario: Run キャンセル
    Given run が存在する:
      | id               | status  |
      | 01HARUN000000001 | running |
    When agent-taskstate run finish --run 01HARUN000000001 --status cancelled
    Then 出力は ok=true である
    And run の status は "cancelled" になる

  Scenario: output_ref 付きで Run 終了
    Given run が存在する:
      | id               | status  |
      | 01HARUN000000001 | running |
    When agent-taskstate run finish --run 01HARUN000000001 --status succeeded --output-ref "agent-taskstate:artifact:01HAART001"
    Then 出力は ok=true である
    And run の output_ref が設定されている

  Scenario: 存在しない run で finish
    Given 空のデータベース
    When agent-taskstate run finish --run 01HANOTFOUND000000001 --status succeeded
    Then 出力は error.code="not_found" である

  Scenario: 既に終了した run を再終了
    Given run が存在する:
      | id               | status    |
      | 01HARUN000000001 | succeeded |
    When agent-taskstate run finish --run 01HARUN000000001 --status failed
    Then 出力は error.code="validation_error" である

  Scenario Outline: 各終了 status
    Given run が存在する:
      | id               | status  |
      | 01HARUN000000001 | running |
    When agent-taskstate run finish --run 01HARUN000000001 --status <status>
    Then 出力は ok=true である

    Examples:
      | status    |
      | succeeded |
      | failed    |
      | cancelled |