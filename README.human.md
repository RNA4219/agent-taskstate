# agent-taskstate Human Guide

このファイルは人間向けの README です。Agent / automation 向けの入口は [README.md](README.md) に分けています。

## これは何か

agent-taskstate は、長期タスクの進行状態をチャット履歴ではなく構造化データとして保持するためのツールです。Task、Decision、Open Question、Run、Context Bundle を明示的に持たせることで、途中再開や検収をしやすくします。

## 何がうれしいか

- 会話ログを読み直さなくても現在地と判断材料を追える
- `typed_ref` で memx や tracker と疎結合に接続できる
- Context Bundle により、再開時に必要な情報をまとめて取り出せる
- SQLite ベースなのでローカルで扱いやすい

## 最初に読む順番

1. [BLUEPRINT.md](BLUEPRINT.md)
2. [docs/src/agent-taskstate_mvp_spec.md](docs/src/agent-taskstate_mvp_spec.md)
3. [EVALUATION.md](EVALUATION.md)
4. [RUNBOOK.md](RUNBOOK.md)

## 目的別の案内

| 目的 | 読むもの |
| --- | --- |
| プロジェクト全体を知りたい | [BLUEPRINT.md](BLUEPRINT.md) |
| 仕様を確認したい | [docs/src/agent-taskstate_mvp_spec.md](docs/src/agent-taskstate_mvp_spec.md), [docs/src/agent-taskstate_sqlite_spec.md](docs/src/agent-taskstate_sqlite_spec.md) |
| 検収したい | [EVALUATION.md](EVALUATION.md), [CHECKLISTS.md](CHECKLISTS.md), `tests/` |
| 実装箇所を追いたい | `src/typed_ref.py`, `src/context_bundle.py`, `src/resolver.py`, `src/tracker_bridge.py` |
| Agent に依頼するときの入口を見たい | [README.md](README.md), [skills/agent-taskstate-maintainer/SKILL.md](skills/agent-taskstate-maintainer/SKILL.md) |

## よく触る場所

| パス | 内容 |
| --- | --- |
| `src/` | コア実装 |
| `tests/` | pytest テスト |
| `docs/schema/agent-taskstate.sql` | 現行 schema |
| `docs/migrations/001_init.sql` | 初期 migration |
| `docs/kv-priority-roadmap/` | 実装優先順と要求の補助資料 |
| `skills/agent-taskstate-maintainer/` | Codex 向け repo 専用 skill |

## 検証コマンド

```bash
pytest -q
```

## Codex Skill

Codex からこの repo を触るときは [`$agent-taskstate-maintainer`](skills/agent-taskstate-maintainer/SKILL.md) を使えます。repo には skill 定義を保存してあり、ローカルの `$CODEX_HOME/skills` にも配置します。

## 補足

GitHub の先頭 README は Agent が読みやすい表形式にしてあります。人が読むときは、この `README.human.md` から入る想定です。
