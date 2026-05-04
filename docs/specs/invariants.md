\# agent-taskstate Invariants Specification



\## 1. Purpose



本仕様は、`agent-taskstate` が不正状態へ崩れないための invariant を定義する。



ここでいう invariant とは、

アプリケーションが常に満たすべき整合条件である。



目的は以下。



\- state / decision / open\_question / run / bundle の意味整合を保つ

\- 実装簡略化のための最低保証を明文化する

\- 長タスク運用中の破綻を早期検知する



---



\## 2. Scope



本仕様の対象は `agent-taskstate` の MVP ドメインモデルである。



\- `task`

\- `task\_state`

\- `decision`

\- `open\_question`

\- `run`

\- `context\_bundle`



対象外:



\- memx 側の保存制約詳細

\- tracker provider ごとの完全整合

\- 外部API認可状態



---



\## 3. Invariant Categories



MVP では invariant を以下の 5 系統に分ける。



\- identity invariants

\- state invariants

\- linkage invariants

\- bundle invariants

\- terminal invariants



---



\## 4. Identity Invariants



\### INV-001: Every Task Has Stable Identity



各 task は一意な `task\_id` を持つ。



\### INV-002: Every Entity Ref Is Canonically Typed



外部参照は `typed\_ref` canonical format に従う。



\### INV-003: Ref Validity And Existence Are Different



`typed\_ref` は形式 valid でも解決不能でありうる。

これは不正状態ではない。



---



\## 5. State Invariants



\### INV-010: Task Has Exactly One Current State



各 task は論理的に current state を 1 つだけ持つ。



実装上は

\- 最新遷移から導出

または

\- materialized current\_state

のどちらでもよいが、

意味論として current state は 1 つでなければならない。



\### INV-011: State Change Must Be Recorded



状態変更は必ず `task\_state` 履歴として記録される。



\### INV-012: State Transition Must Follow Allowed Graph



遷移は `state-machine.md` の許可表に従う。



\### INV-013: Every State Transition Has Reason



すべての遷移は `reason` を持つ。



---



\## 6. Linkage Invariants



\### INV-020: Every Decision Belongs To A Task



各 `decision` は必ず 1 つの task に属する。



\### INV-021: Every Open Question Belongs To A Task



各 `open\_question` は必ず 1 つの task に属する。



\### INV-022: Run Must Belong To A Task Or Bundle



各 `run` は少なくとも以下のどちらかに紐づく。



\- `task\_id`

\- `context\_bundle\_id`



少なくとも片方は non-null とする。



\### INV-023: Bundle Must Preserve Source Refs



各 `context\_bundle` は生成元 `source\_refs` を保持する。



\### INV-024: Decision Evidence Link Must Be Explainable



decision に直接 evidence link がない場合でも、

少なくとも task context 上で説明可能でなければならない。



---



\## 7. Bundle Invariants



\### INV-030: Bundle Must Be Rebuild Output



`context\_bundle` は task に無関係な自由文書であってはならない。

必ず rebuild の出力である。



\### INV-031: Bundle Has Purpose



各 bundle は `purpose` を持つ。



例:

\- `continue\_work`

\- `review\_prepare`

\- `resume\_after\_block`

\- `decision\_support`



\### INV-032: Bundle Has State Snapshot



各 bundle は生成時点の state snapshot を持つ。



\### INV-033: Bundle Source Is Auditable



bundle 生成元が後追いできること。

最低限 `source\_refs` と `generated\_at` を持つ。



---



\## 8. Open Question Invariants



\### INV-040: Active Open Questions Must Be Explicit



未解決事項は `open\_question` として明示される。



\### INV-041: Done Task Should Not Keep Active Open Questions



`done` task には active な open question を原則残さない。



例外:

\- 明示的に「後続 task へ移管済み」と記録されている場合

\- informational residual issue として closure note がある場合



MVP では基本的に未解決を解消または移管してから done とする。



---



\## 9. Terminal State Invariants



\### INV-050: Done And Cancelled Are Terminal



`done`, `cancelled` は terminal state である。



\### INV-051: Terminal Task Must Not Accept New Active Work By Default



terminal state の task に対して

新しい `in\_progress` run を通常作ってはならない。



必要なら新 task を作成する。



\### INV-052: Done Must Be Explainable



`done` task は、少なくとも以下を説明できなければならない。



\- 何を達成したか

\- 何を根拠に done としたか

\- 未解決が残っていないか、残るならどこへ移したか



---



\## 10. Diagnostic Handling



invariant 違反を検知した場合、少なくとも以下の扱いを行う。



\- error として reject

\- warning として記録

\- repair candidate を提示



例:



\- 違反が遷移グラフ破壊なら reject

\- source\_ref 欠落なら warning + repair queue

\- old task の open\_question 残存なら review warning



---



\## 11. Suggested Validation Timing



検証タイミングの推奨は以下。



\- task 作成時

\- state 遷移時

\- decision 追加時

\- open\_question close 時

\- bundle 保存時

\- done / cancelled 遷移時



---



\## 12. Non-Goals



本仕様は以下を扱わない。



\- SQL 制約だけで invariant を完結させること

\- memx / tracker の実在性保証

\- distributed transaction

\- provider 間の時刻整合



---



\## 13. Summary



`agent-taskstate` の MVP invariant の中心は以下。



\- task には current state が 1 つある

\- 状態変更は履歴に残る

\- decision / open\_question は task に属する

\- bundle は source refs を保持する

\- done は説明可能である

\- terminal state は原則再開しない

