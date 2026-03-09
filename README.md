# agent-taskstate

| 読者 | 入口 |
| --- | --- |
| 人間 | [README.human.md](README.human.md) |
| Agent / automation | この README を継続して読む |

## Agent Snapshot

| 項目 | 内容 |
| --- | --- |
| 目的 | 長期タスクの current state / history / decision / question / context bundle を明示的に保持し、チャット履歴なしで再開可能にする |
| 正本 | SQLite 上の構造化状態。会話履歴は正本にしない |
| 主要契約 | `typed_ref` は `<domain>:<entity_type>:<provider>:<entity_id>` の 4 セグメント canonical |
| 主な利用者 | LLM エージェント、CLI 利用の開発者、検収担当 |
| 主な検証コマンド | `pytest -q` |
| 推奨 Skill | [`$agent-taskstate-maintainer`](skills/agent-taskstate-maintainer/SKILL.md) |
| 人間向け概要 | [README.human.md](README.human.md) |

## Read Order

| 優先度 | ファイル | 用途 |
| --- | --- | --- |
| 1 | [BLUEPRINT.md](BLUEPRINT.md) | 目的・制約・背景 |
| 2 | [GUARDRAILS.md](GUARDRAILS.md) | 実装原則・禁止事項 |
| 3 | [docs/src/agent-taskstate_mvp_spec.md](docs/src/agent-taskstate_mvp_spec.md) | MVP の振る舞い仕様 |
| 4 | [docs/src/agent-taskstate_sqlite_spec.md](docs/src/agent-taskstate_sqlite_spec.md) | DB/永続化契約 |
| 5 | [docs/contracts/typed-ref.md](docs/contracts/typed-ref.md) | repo 横断参照契約 |
| 6 | [docs/kv-priority-roadmap/プライオリティ.md](docs/kv-priority-roadmap/プライオリティ.md) | 実装優先順 |

## Task Map

| 作業目的 | 最初に見るもの | 次に見るもの | 触る場所 |
| --- | --- | --- | --- |
| typed_ref の確認 | [docs/contracts/typed-ref.md](docs/contracts/typed-ref.md) | [src/typed_ref.py](src/typed_ref.py) | `src/typed_ref.py`, `tests/test_typed_ref.py` |
| bundle 監査の確認 | [docs/kv-priority-roadmap/02-workx-state-history-and-bundle-audit.md](docs/kv-priority-roadmap/02-workx-state-history-and-bundle-audit.md) | [src/context_bundle.py](src/context_bundle.py) | `src/context_bundle.py`, `tests/test_context_bundle.py` |
| resolver の確認 | [docs/kv-priority-roadmap/03-workx-memx-context-rebuild-resolver.md](docs/kv-priority-roadmap/03-workx-memx-context-rebuild-resolver.md) | [src/resolver.py](src/resolver.py) | `src/resolver.py`, `tests/test_context_rebuild_resolver.py` |
| tracker 連携の確認 | [docs/kv-priority-roadmap/04-tracker-bridge-minimum-integration.md](docs/kv-priority-roadmap/04-tracker-bridge-minimum-integration.md) | [src/tracker_bridge.py](src/tracker_bridge.py) | `src/tracker_bridge.py`, `tests/test_tracker_bridge.py` |
| 受入確認 | [EVALUATION.md](EVALUATION.md) | [CHECKLISTS.md](CHECKLISTS.md) | `tests/`, `docs/tests/*.feature` |
| Codex で repo 専用運用 | [skills/agent-taskstate-maintainer/SKILL.md](skills/agent-taskstate-maintainer/SKILL.md) | [README.human.md](README.human.md) | `skills/agent-taskstate-maintainer/`, `README.md` |

## Runtime Surface

| 種別 | エントリ |
| --- | --- |
| コア実装 | `src/typed_ref.py`, `src/context_bundle.py`, `src/resolver.py`, `src/tracker_bridge.py`, `src/state_transition.py` |
| テスト | `tests/` |
| schema | `docs/schema/agent-taskstate.sql`, `docs/migrations/001_init.sql` |
| 参考実装 | `docs/src/agent-taskstate_cli.py` |
| repo skill | `skills/agent-taskstate-maintainer/` |

## Verification

| 目的 | コマンド |
| --- | --- |
| 全テスト | `pytest -q` |
| typed_ref 周辺 | `pytest -q tests/test_typed_ref.py` |
| bundle 周辺 | `pytest -q tests/test_context_bundle.py tests/test_context_rebuild_resolver.py` |
| tracker 周辺 | `pytest -q tests/test_tracker_bridge.py` |
| skill 検証 | `python C:/Users/ryo-n/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/agent-taskstate-maintainer` |

## Output Expectations

| 項目 | 期待値 |
| --- | --- |
| 実装変更 | 仕様差分がある場合は対応テストも更新 |
| レビュー報告 | バグ・未達・回帰リスクを先に列挙 |
| 完了条件 | テスト通過、必要なら schema/doc 更新、コミット作成 |
| 人間の案内先 | [README.human.md](README.human.md) |
