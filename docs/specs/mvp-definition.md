\# agent-taskstate MVP Definition



\## 1. Purpose



本仕様は、`agent-taskstate` MVP を「何が揃えば実装着手・最低完成とみなすか」で定義する。



---



\## 2. Documentation DoD



以下の文書が存在すること。



\- `requirements.md`

\- `docs/contracts/typed-ref.md`

\- `docs/specs/state-machine.md`

\- `docs/specs/context-rebuild.md`

\- `docs/specs/invariants.md`

\- `docs/specs/service-boundaries.md`

\- `schema/agent-taskstate.sql`

\- `migrations/001\_init.sql`



---



\## 3. Functional DoD



\### 3.1 Task Lifecycle



以下ができること。



\- task を作成できる

\- `proposed -> ready -> in\_progress -> review -> done` を通せる

\- `blocked` へ遷移し、解除できる

\- 違反遷移は reject される



\### 3.2 Decision / Open Question



以下ができること。



\- decision を task に追加できる

\- decision に `typed\_ref` をぶら下げられる

\- open question を追加・解消できる



\### 3.3 Context Rebuild



以下ができること。



\- task から `L1` bundle を生成できる

\- bundle に `source\_refs` が入る

\- bundle 生成履歴を取得できる



\### 3.4 Run



以下ができること。



\- run を開始できる

\- run を成功終了できる

\- run を失敗終了できる

\- state 遷移や rebuild と run を紐づけられる



---



\## 4. Test DoD



\### 4.1 State Machine



\- 許可遷移は通る

\- 不許可遷移は落ちる

\- terminal state からの復帰は落ちる



\### 4.2 Invariants



\- current state が 1 つになる

\- run が `task\_id/context\_bundle\_id` 両方 null だと落ちる

\- done task に active open question が残ると警告または失敗



\### 4.3 Context Rebuild



\- source refs が空でない

\- `L1` は summary-only

\- `L2` で selected ref が増える



---



\## 5. Non-Goals For MVP



MVP では以下を必須にしない。



\- 高度な reranking

\- memx との自動深連携

\- tracker provider 個別最適化

\- 権限モデルの厳密設計

\- reopen workflow

\- 複雑な優先度計算

\- 高度な dashboard



---



\## 6. Exit Condition



MVP を完了とみなす条件は以下。



\- 最小スキーマが migration で作成できる

\- 状態遷移サービスが動く

\- decision / open question が task に結び付く

\- `L1` context rebuild が保存付きで動く

\- 最低限の invariant が落ちない

\- 1 つの実データシナリオを end-to-end で通せる



---



\## 7. Summary



`agent-taskstate` MVP は、長タスクを外部状態として扱い、

状態遷移・判断・未解決論点・文脈再構成を最小構成で回せる状態を指す。

