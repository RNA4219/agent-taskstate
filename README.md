# agent-taskstate Agent README

人間向けの概要は [README-human.md](README-human.md) を参照してください。

## 同梱 Skill

- Skill 名: `$agent-taskstate-maintainer`
- 格納先: `skills/agent-taskstate-maintainer/`
- 入口: `skills/agent-taskstate-maintainer/SKILL.md`

## 最初に読む順番

| 順番 | ファイル |
|------|----------|
| 1 | `skills/agent-taskstate-maintainer/SKILL.md` |
| 2 | `BLUEPRINT.md` |
| 3 | `docs/kv-priority-roadmap/` |

必要になった時だけ参照:
`GUARDRAILS.md` / `docs/src/agent-taskstate_mvp_spec.md` / `docs/src/agent-taskstate_sqlite_spec.md` / `docs/src/agent-taskstate_phase2_pulse_kestra_spec.md` / `docs/contracts/typed-ref.md` / `README-human.md`

## 実施ルール

| 項目 | ルール |
|------|--------|
| 優先順 | `P1 -> P2 -> P3 -> P4` を崩さない |
| 正本 | 内部 task state の正本は `agent-taskstate`。会話履歴を正本にしない |
| typed_ref | 新規出力は `<domain>:<entity_type>:<provider>:<entity_id>` の 4 セグメント canonical |
| 監査性 | `context_bundle` の raw inclusion、diagnostics、generator metadata を落とさない |
| 変更単位 | 振る舞い変更時は実装、テスト、schema/doc を同時に更新する |

## 検証

```bash
pytest -q
```

## 参照

- `docs/RUNBOOK.md`
- `docs/EVALUATION.md`
- `docs/CHECKLISTS.md`
- `docs/src/agent-taskstate_mvp_spec.md`
- `docs/src/agent-taskstate_sqlite_spec.md`
- `docs/src/agent-taskstate_phase2_pulse_kestra_spec.md`
- `docs/schema/agent-taskstate.sql`
- `docs/contracts/typed-ref.md`
