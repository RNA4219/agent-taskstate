# typed_ref 契約（agent-taskstate 1.1.0）

canonical形式は4セグメントに固定する。

```
<domain>:<entity_type>:<provider>:<entity_id>
```

例:

- `agent-taskstate:task:local:task_01J...`
- `agent-taskstate:decision:local:dec_01J...`
- `agent-taskstate:question:local:q_01J...`
- `memx:evidence:local:ev_01J...`
- `memx:artifact:local:art_01J...`
- `tracker:issue:jira:PROJ-123`
- `tracker:issue:github:owner/repo#123`

書き込みは常に4セグメントを出力する。移行期間の読み込みだけ3セグメント
（providerは`local`）を受理し、DBの既存値を一括更新しない。保存対象の
artifact、evidence、input、output、bundle sourceは保存前にcanonicalize・検証する。

検証責務:

- 4セグメントへ分割できること
- 全セグメントが空でないこと
- domainが`agent-taskstate`、`memx`、`tracker`のいずれかであること
- 実在性確認と外部APIアクセスはresolver/adapterの責務であること

秘密情報やURL全体をtyped_refのentity_idへ埋め込まない。
