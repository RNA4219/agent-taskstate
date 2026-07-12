# agent-taskstate 1.1.0仕様

## 正本

実装正本は `src/agent_taskstate/`、DB正本は
`docs/schema/agent-taskstate.sql`、migration正本は
`src/agent_taskstate/migrations/` と `docs/migrations/` です。

## 受入契約

- 既存plural DBを保持し、schema_versionで冪等migrationする。
- task作成とstatus変更をstate_transitionsへappendする。
- context bundleは完全snapshotで、purpose、rebuild level、summary、digest、
  diagnostics、raw flag、generator version、generated timestamp、sourcesを持つ。
- resolver未設定はunsupported diagnosticsとして保存し、bundle buildは継続する。
- 予期しない例外はinternal_error、概要はstdout、tracebackはstderrである。
