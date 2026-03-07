\# agent-taskstate State Machine Specification



\## 1. Purpose



本仕様は、`agent-taskstate` における task の状態遷移を定義する。



目的は以下の通り。



\- task の現在位置を明示する

\- 遷移可能条件を統一する

\- run / decision / review と整合する

\- 長タスクを会話履歴ではなく状態管理で運用可能にする



---



\## 2. Scope



本仕様の対象は `task` の lifecycle である。



対象外:



\- issue tracker 側の個別状態

\- memx 側保存ポリシー

\- 人間組織の承認フロー詳細



---



\## 3. States



MVP では task state を以下に限定する。



\- `proposed`

\- `ready`

\- `in\_progress`

\- `blocked`

\- `review`

\- `done`

\- `cancelled`



---



\## 4. State Definitions



\### 4.1 proposed



まだ着手準備が完了していない状態。

論点整理・依存確認・入力待ちなどを含む。



\### 4.2 ready



着手可能な状態。

必要最低限の入力・依存・目的が揃っている。



\### 4.3 in\_progress



作業進行中の状態。

LLM / human / automation により、実際の処理が進んでいる。



\### 4.4 blocked



何らかの障害により前進不能な状態。

依存待ち、証拠不足、権限不足、外部回答待ちなどを含む。



\### 4.5 review



成果物または判断内容の検証中状態。

self-review / peer-review / operator-check を含む。



\### 4.6 done



完了状態。

目的達成または受入条件充足が確認された状態。



\### 4.7 cancelled



中止状態。

価値消失、方針変更、重複、外部要因などで終了した状態。



---



\## 5. Allowed Transitions



MVP で許可する遷移は以下のみ。



\- `proposed -> ready`

\- `ready -> in\_progress`

\- `in\_progress -> blocked`

\- `blocked -> in\_progress`

\- `in\_progress -> review`

\- `review -> in\_progress`

\- `review -> done`

\- `proposed -> cancelled`

\- `ready -> cancelled`

\- `in\_progress -> cancelled`

\- `blocked -> cancelled`

\- `review -> cancelled`



`done` から他状態への復帰は MVP では禁止する。

必要になった場合は reopen ではなく新 task を起票する。



---



\## 6. Transition Semantics



\### 6.1 proposed -> ready



条件例:



\- task description がある

\- owner または actor 種別が定まっている

\- 入力不足が致命的でない

\- 最低限の進行単位として成立している



\### 6.2 ready -> in\_progress



条件例:



\- 実行主体が決まっている

\- current attempt を開始できる

\- bundle 再構成に必要な最小入力が存在する



\### 6.3 in\_progress -> blocked



条件例:



\- 外部依存が未解決

\- 証拠不足で判断不能

\- 実行エラーから前進不能

\- review 前提を満たせない



\### 6.4 blocked -> in\_progress



条件例:



\- block reason が解消された

\- 代替ルートが見つかった

\- 必須入力が追加された



\### 6.5 in\_progress -> review



条件例:



\- 成果物または判断案が揃った

\- 現時点の出力を検証段階へ回せる

\- 最低限の evidence / artifact / decision が残っている



\### 6.6 review -> in\_progress



条件例:



\- 差し戻し

\- 修正要求

\- 根拠不足

\- open question 再発



\### 6.7 review -> done



条件例:



\- 受入可能

\- 主要 open question が解消済み

\- 必須 artifact / decision が揃っている

\- 終了根拠を説明可能



\### 6.8 \* -> cancelled



条件例:



\- task が不要化

\- 上位方針の変更

\- 重複 task の整理

\- コストに対して価値が消失



---



\## 7. State History Model



`agent-taskstate` は current state のみを truth とせず、

\*\*遷移履歴そのものを truth\*\* とみなす。



`task\_state` には少なくとも以下を記録する。



\- `task\_id`

\- `from\_state`

\- `to\_state`

\- `reason`

\- `actor\_type`

\- `actor\_id`

\- `run\_id` (nullable)

\- `changed\_at`



current state は最新遷移から導出または materialize する。



---



\## 8. Actor Model



状態遷移を発生させる actor は以下のいずれか。



\- `human`

\- `agent`

\- `system`



必要に応じて `actor\_id` を保持する。



例:



\- `human:ryo`

\- `agent:planner`

\- `system:sync\_worker`



---



\## 9. State Transition Rules



\### 9.1 Every Transition Must Have Reason



すべての遷移は `reason` を持つ。



悪い例:

\- `done`



良い例:

\- `review passed; acceptance criteria satisfied`

\- `blocked by missing tracker issue permissions`



\### 9.2 Silent Transition Is Prohibited



状態変更は履歴なしに直接更新してはならない。



\### 9.3 Review Is Not Optional in Principle



MVP では小規模 task について簡略 review を許してよいが、

状態上は `in\_progress -> review -> done` を基本経路とする。



---



\## 10. Terminal States



以下を terminal state とする。



\- `done`

\- `cancelled`



MVP では terminal state からの復帰は禁止。



---



\## 11. Non-Goals



本仕様は以下を扱わない。



\- priority 計算

\- SLA 管理

\- tracker 側ステータスとの完全一致

\- 組織固有承認ルート



---



\## 12. Summary



MVP state machine の基本思想は以下。



\- 状態数は増やしすぎない

\- current state より遷移履歴を重視する

\- reason を必須化する

\- long-task の進行を明示状態で保持する

