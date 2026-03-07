\# agent-taskstate Service Boundaries



\## 1. Purpose



本仕様は、`agent-taskstate` の MVP 実装におけるサービス境界を定義する。



目的は以下の通り。



\- 状態変更責務を一点に集約する

\- repository と domain logic の境界を明確にする

\- 実装時の責務混濁を防ぐ

\- Phase 1 実装の単位を明示する



---



\## 2. Services



MVP では以下のサービスを持つ。



\- `TaskService`

\- `StateTransitionService`

\- `DecisionService`

\- `OpenQuestionService`

\- `ContextRebuildService`

\- `RunService`



---



\## 3. TaskService



\### Responsibilities



\- task 作成

\- task 取得

\- task 更新

\- task link 追加

\- task summary 取得



\### Minimum Interface



```txt

CreateTask(input) -> Task

GetTask(task\_id) -> Task

UpdateTaskMeta(task\_id, patch) -> Task

ListTaskLinks(task\_id) -> \[TaskLink]

AddTaskLink(task\_id, typed\_ref, link\_type, role) -> TaskLink

GetTaskOverview(task\_id) -> TaskOverview

```



---



\## 4. StateTransitionService



\### Responsibilities



\- state machine の唯一の入口

\- 遷移可否判定

\- `task\_state` 履歴追加

\- `task.status` materialized 更新

\- terminal state 禁止制御



\### Minimum Interface



```txt

CanTransition(from\_state, to\_state) -> bool

TransitionTask(task\_id, to\_state, reason, actor\_type, actor\_id, run\_id?) -> TaskState

GetCurrentState(task\_id) -> State

ListStateHistory(task\_id) -> \[TaskState]

```



\### Important Rule



`task.status` を直接更新するコードを他所に置かないこと。



---



\## 5. DecisionService



\### Responsibilities



\- decision 作成

\- supersede / withdraw

\- decision root ref 追加

\- active decision 取得



\### Minimum Interface



```txt

CreateDecision(input) -> Decision

AttachDecisionRef(decision\_id, typed\_ref, ref\_type, role) -> DecisionRef

ListActiveDecisions(task\_id) -> \[Decision]

SupersedeDecision(decision\_id, note?) -> Decision

WithdrawDecision(decision\_id, note?) -> Decision

```



---



\## 6. OpenQuestionService



\### Responsibilities



\- 未解決論点管理

\- 根拠 ref 付与

\- resolve / drop / migrate



\### Minimum Interface



```txt

CreateOpenQuestion(input) -> OpenQuestion

AttachOpenQuestionRef(open\_question\_id, typed\_ref, role) -> OpenQuestionRef

ListActiveOpenQuestions(task\_id) -> \[OpenQuestion]

ResolveOpenQuestion(open\_question\_id, resolution\_note) -> OpenQuestion

DropOpenQuestion(open\_question\_id, resolution\_note) -> OpenQuestion

MigrateOpenQuestion(open\_question\_id, resolution\_note) -> OpenQuestion

```



---



\## 7. ContextRebuildService



\### Responsibilities



\- task をもとに bundle を組み立てる

\- rebuild level ごとの入力調整

\- source refs 記録

\- partial failure を bundle と診断に落とす



\### Minimum Interface



```txt

RebuildContext(task\_id, purpose, rebuild\_level, options?) -> ContextBundle

GetLatestBundle(task\_id) -> ContextBundle?

ListBundles(task\_id) -> \[ContextBundle]

```



\### Supporting Interface



```txt

CollectSourceRefs(task\_id, rebuild\_level) -> SourceSet

ComposeBundle(source\_set, purpose, rebuild\_level) -> BundlePayload

PersistBundle(bundle\_payload, source\_refs) -> ContextBundle

```



---



\## 8. RunService



\### Responsibilities



\- run の開始・終了記録

\- 実行ログ要約保存

\- 失敗時エラー要約保存



\### Minimum Interface



```txt

StartRun(input) -> Run

FinishRunSuccess(run\_id, output\_summary) -> Run

FinishRunFailure(run\_id, error\_message, output\_summary?) -> Run

ListRuns(task\_id) -> \[Run]

```



---



\## 9. Service Boundary Rules



\- state 遷移は `StateTransitionService` に集約する

\- bundle 生成は `ContextRebuildService` に集約する

\- `typed\_ref` 解決は repository ではなく service/helper 側責務とする

\- repository は CRUD に寄せ、意味判断を持ちすぎない

\- invariant 検査は service 層で行う



---



\## 10. Summary



MVP では、task 管理・状態遷移・判断・未解決論点・文脈再構成・実行記録を

別サービスとして切り分けることで、責務の濁りを防ぐ。

