\# Context Rebuild Specification



\## 1. Purpose



本仕様は、`agent-taskstate` が long-task を会話履歴や KV cache に依存せず継続するための

`context rebuild` 手順を定義する。



目的は以下の通り。



\- 必要文脈だけを都度再構成する

\- LLM に渡す入力を安定化する

\- 判断根拠と bundle 生成元を追跡可能にする

\- raw evidence と圧縮状態を使い分ける



---



\## 2. Core Principle



`agent-taskstate` における context rebuild の原則は以下。



\- 常時フル履歴は持たない

\- 外部状態から必要文脈を組み立てる

\- 普段は圧縮状態を使う

\- 重要局面だけ raw に降りる

\- bundle 自体を保存して再現可能にする



---



\## 3. Inputs



`context rebuild` の入力元は以下。



\### 3.1 Mandatory Inputs



\- `task`

\- current `task\_state`

\- active `open\_question`

\- recent `decision`

\- latest relevant `artifact` refs

\- latest relevant `evidence` or `knowledge` refs

\- rebuild request metadata



\### 3.2 Optional Inputs



\- tracker issue snapshot

\- previous run summary

\- failure summary

\- operator note

\- explicit raw evidence request



---



\## 4. Output



`context rebuild` の出力は `context\_bundle` である。



`context\_bundle` は少なくとも以下を含む。



\- `bundle\_id`

\- `task\_id`

\- `purpose`

\- `summary`

\- `state\_snapshot`

\- `decision\_digest`

\- `open\_question\_digest`

\- `evidence\_refs`

\- `artifact\_refs`

\- `tracker\_refs`

\- `source\_refs`

\- `raw\_included`

\- `generated\_at`



---



\## 5. Rebuild Levels



MVP では rebuild level を 3 段階とする。



\### 5.1 L1: Summary-Only



圧縮状態中心。

通常の継続作業、軽微更新、状況把握に使用する。



含むもの:



\- task 要約

\- current state

\- active open questions

\- recent decisions

\- related refs 一覧



\### 5.2 L2: Summary + Selected Evidence



圧縮状態に加えて、必要箇所の raw evidence を限定添付する。



使用例:



\- 判断根拠確認

\- review 前チェック

\- 差し戻し調査

\- conflicting facts 解消



\### 5.3 L3: Raw-Heavy



重要局面で raw を多めに投入する。



使用例:



\- 最終判断直前

\- 根拠衝突

\- 誤判定疑い

\- 再現困難なバグ調査



MVP では L3 は手動または明示条件でのみ使用する。



---



\## 6. Rebuild Procedure



標準 rebuild 手順は以下。



\### Step 1. Load Task Core



\- task 本体を読む

\- title / objective / scope / owner / status を取得



\### Step 2. Load Current State



\- 最新 state transition を取得

\- current state と block reason を反映



\### Step 3. Load Open Questions



\- active な open question を取得

\- 優先度順または時系列順に並べる



\### Step 4. Load Decisions



\- 最新 decision を数件取得

\- 現状に効いている判断のみを残す



\### Step 5. Load Linked Evidence / Artifacts / Tracker Refs



\- task に紐づく typed\_ref 群を収集

\- rebuild level に応じて要約または raw を添付



\### Step 6. Compose Digest



以下を bundle 用に圧縮する。



\- 現在地

\- 何が決まっているか

\- 何が未解決か

\- 次に何をすべきか

\- 必要なら参照すべき証拠は何か



\### Step 7. Persist Context Bundle



生成した bundle を保存する。

生成元 `source\_refs` も同時に保持する。



---



\## 7. Bundle Shape



MVP の conceptual shape は以下。



```json

{

&nbsp; "bundle\_id": "cb\_01J...",

&nbsp; "task\_ref": "agent-taskstate:task:local:task\_01J...",

&nbsp; "purpose": "continue\_work",

&nbsp; "state\_snapshot": {

&nbsp;   "current\_state": "in\_progress",

&nbsp;   "last\_reason": "working on migration draft"

&nbsp; },

&nbsp; "decision\_digest": \[

&nbsp;   {

&nbsp;     "ref": "agent-taskstate:decision:local:dec\_01J...",

&nbsp;     "summary": "typed\_ref is 4-segment canonical string"

&nbsp;   }

&nbsp; ],

&nbsp; "open\_question\_digest": \[

&nbsp;   {

&nbsp;     "ref": "agent-taskstate:open\_question:local:oq\_01J...",

&nbsp;     "summary": "when should raw evidence be included?"

&nbsp;   }

&nbsp; ],

&nbsp; "evidence\_refs": \[

&nbsp;   "memx:evidence:local:ev\_01J..."

&nbsp; ],

&nbsp; "artifact\_refs": \[

&nbsp;   "memx:artifact:local:art\_01J..."

&nbsp; ],

&nbsp; "tracker\_refs": \[

&nbsp;   "tracker:issue:github:RNA4219/agent-taskstate#12"

&nbsp; ],

&nbsp; "raw\_included": false,

&nbsp; "source\_refs": \[

&nbsp;   "agent-taskstate:task:local:task\_01J...",

&nbsp;   "agent-taskstate:decision:local:dec\_01J...",

&nbsp;   "memx:evidence:local:ev\_01J..."

&nbsp; ]

}

```



---



\## 8. Raw Descent Rules



MVP では raw 降下条件を以下のように定義する。



\### 8.1 Raw Inclusion Triggers



以下のいずれかで raw inclusion を許可する。



\- review 直前

\- decision root cause 確認

\- conflicting summary がある

\- open question が証拠依存

\- operator が明示要求

\- prior output の信頼性が低い



\### 8.2 Raw Inclusion Limit



raw は常時全面添付しない。

必要箇所のみ selected inclusion とする。



---



\## 9. Rebuild Triggers



`context rebuild` を発火する代表条件は以下。



\- task を再開するとき

\- state が変わるとき

\- review に入るとき

\- block 解除後

\- 新 evidence / artifact が入ったとき

\- tracker 側の重要更新を反映するとき

\- run 再試行時



---



\## 10. Persistence Policy



`context\_bundle` は使い捨てではなく保存する。



理由:



\- 何を見て判断したか追跡できる

\- 再現性が上がる

\- review / debugging がしやすい

\- 将来の bundle 改善比較に使える



保存する最低項目:



\- bundle body

\- generated\_at

\- generator version

\- source refs

\- rebuild level



---



\## 11. Failure Handling



rebuild に失敗した場合は以下を返す。



\- `partial\_bundle`

\- `missing\_refs`

\- `unsupported\_refs`

\- `diagnostic\_message`



完全失敗でも task 自体を壊してはならない。



---



\## 12. Non-Goals



本仕様では以下を扱わない。



\- embedding / reranker 詳細

\- LLM prompt 文面

\- memx 内部検索アルゴリズム

\- tracker provider ごとの同期細部



---



\## 13. Summary



`context rebuild` のMVP原則は以下。



\- 毎回必要文脈だけ組み立てる

\- 普段は summary 中心

\- 重要局面だけ raw に降りる

\- bundle を保存して再現可能にする

