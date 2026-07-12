# agent-taskstate 1.1.0

長期タスクの現在地、状態履歴、再開用context bundleをSQLiteへ保存するローカルCLIです。

```powershell
agent-taskstate init
agent-taskstate task create --json '{"kind":"feature","title":"Example","goal":"Ship it"}'
agent-taskstate task history --task <task-id>
agent-taskstate context build --task <task-id> --reason normal --rebuild-level L2
```

外部trackerは補助情報です。接続設定には秘密値を保存せず、環境変数名だけを保存します。
