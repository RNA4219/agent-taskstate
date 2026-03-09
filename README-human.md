# agent-taskstate

Agent 向けの正本は [README.md](README.md) を参照してください。  
このファイルは、人間がリポジトリの目的、責務、構成、読み方を理解するための説明用 README です。

agent-taskstate は、長期タスクの進行状態をチャット履歴ではなく構造化データとして保持するための状態管理ツールです。Task、Task State、Decision、Open Question、Run、Context Bundle を明示的に持ち、再開、レビュー、検収を会話ログ依存にせず進められるようにします。

## 保守方針

この repo では `docs/kv-priority-roadmap/` を補助要求として扱い、以後の変更でも整合を維持します。

- 要求、実装、テスト、SQL、README の差分を放置しない
- `typed_ref` の canonical 形式と repo 間の疎結合を崩さない
- `context_bundle` の監査性と再開容易性を維持する

## このリポジトリがやること

- internal task の current state と履歴を SQLite 上で保持する
- decision、open question、run、context bundle を task と結び付けて保持する
- 会話履歴を読み直さなくても再開できるよう、context rebuild 用の材料を残す
- `typed_ref` で `memx-core` や `tracker-bridge` と疎結合に接続する
- task 単位の export と検収しやすい状態表現を提供する

## やらないこと

- 自律実行ランタイムそのものを提供すること
- 複数エージェント協調制御を持つこと
- 外部 tracker の完全同期や完全ミラーを行うこと
- GUI / Web UI、認可、分散構成を MVP に含めること

## 位置づけ

この repo の責務は「内部 task state の正本を持つこと」にあります。

- `agent-taskstate`
  - task、task_state、decision、open_question、run、context_bundle の正本
- `memx-core`
  - knowledge、evidence、summary などの正本
- `tracker-bridge`
  - 外部 tracker との接続、投影、リンク、同期監査の正本

この分離により、内部の作業状態、外部 issue、知識ストアを混ぜずに扱えます。

## 典型的な使い方

### 1. task と state を作る

task を作成し、`task_state` に current step、constraints、done_when、summary を置きます。  
これにより、会話履歴を読まずに現在地を復元できます。

### 2. 判断と未解決事項を蓄積する

decision と open question を履歴として追加し、必要に応じて accept / reject / answer / defer を行います。  
run を記録しておくことで、いつ何を試したかも追跡できます。

### 3. review / recovery 用に bundle を作る

`context_bundle` は source refs、selected raw、metadata、diagnostics をまとめ、再開やレビュー時の材料を残します。  
resolver は task の current state と外部参照を組み合わせて再構成に必要な文脈を返します。

## 主要な設計ルール

### Agent-First

- 人間向け装飾よりも、機械が叩きやすい安定した入出力を優先します
- CLI 出力は将来の API / MCP に写像しやすい形を維持します

### Chat-History-Free

- チャット履歴を正本にしません
- 再開は `task_state` と `context_bundle` の再構成で行います

### Append-Oriented

- `decision`、`open_question`、`run`、`context_bundle` は履歴を残します
- 上書きよりも追加と状態更新を優先します

### Loose Coupling

- repo 間の参照は `typed_ref` による論理参照で扱います
- DB 横断 FK は持ちません

### typed_ref を canonical に保つ

新規に扱う参照は次の 4 セグメント形式を前提にします。

```text
<domain>:<entity_type>:<provider>:<entity_id>
```

例:

- `agent-taskstate:task:local:01JABCDEF...`
- `memx:evidence:local:01JXYZ...`
- `tracker:issue:jira:PROJ-123`

## 最小データモデル

### `task`

到達目標と所有者、優先度、状態機械を持つ基本単位です。

### `task_state`

最新版の軽量ダッシュボードです。`current_step`、`constraints`、`done_when`、`current_summary` を持ちます。

### `decision`

何を、なぜ決めたかを履歴として残します。

### `open_question`

未解決事項と回答状態を保持します。

### `run`

実行試行の開始と終了を記録します。

### `context_bundle`

再開やレビューに必要な source refs、selected raw、metadata、diagnostics を束ねます。

## リポジトリ構成

| パス | 内容 |
|------|------|
| `src/` | コア実装 |
| `tests/` | pytest テスト |
| `docs/src/` | MVP / SQLite 仕様 |
| `docs/schema/agent-taskstate.sql` | 現行 schema |
| `docs/migrations/001_init.sql` | 初期 migration |
| `docs/contracts/typed-ref.md` | repo 横断参照契約 |
| `docs/kv-priority-roadmap/` | 実装優先順と補助要求 |
| `skills/agent-taskstate-maintainer/` | repo 同梱 Codex skill |
| `RUNBOOK.md` | 実行と検証手順 |
| `EVALUATION.md` | 検収観点 |

## 読み始める順番

### 人間が全体像を掴みたい場合

1. `README-human.md`
2. `BLUEPRINT.md`
3. `docs/src/agent-taskstate_mvp_spec.md`
4. `docs/src/agent-taskstate_sqlite_spec.md`
5. `RUNBOOK.md`

### 実装やレビューに入る場合

1. `README.md`
2. `skills/agent-taskstate-maintainer/SKILL.md`
3. `BLUEPRINT.md`
4. `docs/kv-priority-roadmap/`

## クイックスタート

```bash
pytest -q
```

## この repo で確認しやすいこと

- task state の状態遷移と optimistic lock が正しく機能するか
- `typed_ref` の canonical 化が一貫しているか
- `context_bundle` の監査項目が永続化されているか
- resolver が再開に必要な文脈を組み立てられるか
- tracker bridge との最小連携が typed_ref ベースで保たれているか
- 要求、SQL、実装、テストの整合が取れているか

## Agent / OSS 配布について

この repo は Agent ファーストの前提で、repo 内に skill を同梱しています。  
Codex などの Agent は [skills/agent-taskstate-maintainer/SKILL.md](skills/agent-taskstate-maintainer/SKILL.md) を入口に、要求確認、レビュー、修正、テスト、受入確認を進められます。

一方で、運用者やレビュー担当者向けの説明はこの `README-human.md` に集約します。  
つまり、`README.md` は最小導線、`README-human.md` は背景説明、`SKILL.md` は Agent 実務手順、という分担です。

## 参照

- Agent 向け入口: [README.md](README.md)
- repo 同梱 skill: [skills/agent-taskstate-maintainer/SKILL.md](skills/agent-taskstate-maintainer/SKILL.md)
- 設計: [BLUEPRINT.md](BLUEPRINT.md)
- 要件: [docs/src/agent-taskstate_mvp_spec.md](docs/src/agent-taskstate_mvp_spec.md)
- DB: [docs/src/agent-taskstate_sqlite_spec.md](docs/src/agent-taskstate_sqlite_spec.md)
- SQL: [docs/schema/agent-taskstate.sql](docs/schema/agent-taskstate.sql)
- 実行: [RUNBOOK.md](RUNBOOK.md)
- 検収: [EVALUATION.md](EVALUATION.md)

## ライセンス

MIT
