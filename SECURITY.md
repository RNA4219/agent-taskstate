# Security Policy

- token、password、secret、api_keyの平文をDBやログへ保存しない。
- tracker接続は非秘密設定とsecret environment variable名を分離する。
- 外部trackerへのcomment/status操作は明示CLIコマンドだけで実行する。
- 不具合報告では秘密値、個人情報、実データを添付しない。
