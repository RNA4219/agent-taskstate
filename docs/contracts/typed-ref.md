\# Typed Ref Contract



\## 1. Purpose



本仕様は、`agent-taskstate` が `memx-core` / `tracker-bridge` / 外部 tracker と疎結合に連携するための

共通参照表現 `typed\_ref` を定義する。



`typed\_ref` は DB 横断 FK を用いずに、外部エンティティを識別・保持・再解決するための

文字列契約である。



---



\## 2. Design Goals



`typed\_ref` の設計目標は以下の通り。



\- repo 間を疎結合に保つ

\- 文字列として保存・比較・転送できる

\- 参照解決失敗時も値を保持できる

\- 人間にも最低限読める

\- 将来の provider / entity type 追加に耐える



---



\## 3. Canonical Format



\### 3.1 Basic Form



`typed\_ref` の canonical format は以下とする。



```txt

<domain>:<entity\_type>:<provider>:<entity\_id>

```



例:



\- `agent-taskstate:task:local:task\_01JXYZ...`

\- `agent-taskstate:decision:local:dec\_01JXYZ...`

\- `memx:evidence:local:ev\_01JXYZ...`

\- `memx:artifact:local:art\_01JXYZ...`

\- `tracker:issue:github:owner/repo#123`

\- `tracker:issue:jira:PROJ-123`



\### 3.2 Segment Definitions



\- `domain`

&nbsp; - 管轄ドメインを表す

&nbsp; - 例: `agent-taskstate`, `memx`, `tracker`



\- `entity\_type`

&nbsp; - エンティティ種別を表す

&nbsp; - 例: `task`, `decision`, `evidence`, `artifact`, `issue`



\- `provider`

&nbsp; - 発行主体または解決主体を表す

&nbsp; - 例: `local`, `github`, `jira`



\- `entity\_id`

&nbsp; - provider 内での識別子

&nbsp; - 例: `task\_01...`, `PROJ-123`, `owner/repo#123`



---



\## 4. Allowed Character Rules



\### 4.1 Separator



セグメント区切りは `:` を用いる。



\### 4.2 Reserved Rule



`domain`, `entity\_type`, `provider` は `:` を含んではならない。



`entity\_id` は原則自由だが、保存時はアプリケーション層で正規化する。

必要に応じて URL-safe な表現へ変換してもよい。



\### 4.3 Case Rule



\- `domain`, `entity\_type`, `provider` は lowercase canonical とする

\- `entity\_id` は provider の原表記を優先する

\- 比較時は完全一致を基本とする



---



\## 5. Canonical Examples



\### 5.1 Local Entities



\- `agent-taskstate:task:local:task\_01JABCDEF`

\- `agent-taskstate:context\_bundle:local:cb\_01JABCDEF`

\- `memx:evidence:local:ev\_01JABCDEF`



\### 5.2 External Tracker Entities



\- `tracker:issue:github:RNA4219/agent-taskstate#12`

\- `tracker:issue:jira:PLAT-204`

\- `tracker:issue:linear:agent-taskstate-17`



---



\## 6. Validation Rules



`typed\_ref` として有効とみなす条件は以下。



\- 4 セグメントに分割可能である

\- `domain` が既知の namespace に属する

\- `entity\_type` が空文字でない

\- `provider` が空文字でない

\- `entity\_id` が空文字でない



\### 6.1 Important Note



`typed\_ref` の妥当性と、参照先の実在性は別である。



つまり、



\- 形式的に valid

\- ただし解決不能



という状態を許容する。



---



\## 7. Resolution Semantics



`typed\_ref` の解決は DB 制約ではなく、アプリケーション層責務とする。



\### 7.1 Resolution Result



解決結果は少なくとも以下の 3 状態を持つ。



\- `resolved`

\- `unresolved`

\- `unsupported`



\### 7.2 Resolution Failure



参照解決に失敗しても `typed\_ref` 自体は削除しない。

失敗はイベントまたは診断結果として別途記録する。



---



\## 8. Usage in agent-taskstate



`agent-taskstate` では以下の用途で `typed\_ref` を使用する。



\- related evidence 参照

\- related artifact 参照

\- tracker issue 参照

\- context bundle source list

\- decision の根拠参照

\- open question の関連対象参照



---



\## 9. Non-Goals



本仕様では以下を扱わない。



\- 各 provider ごとの API 解決手順

\- 参照先の認可・認証

\- URL 形式の標準化

\- repo 間 FK 制約



---



\## 10. Future Extensions



将来的に必要であれば以下を追加できる。



\- version suffix

\- fragment / subresource 指定

\- entity snapshot hash

\- canonical URI との双方向変換



例:



```txt

memx:evidence:local:ev\_01JABCDEF@v3

```



ただし MVP では採用しない。



---



\## 11. Contract Summary



\- `typed\_ref` は 4 セグメント文字列

\- repo 間 FK は張らない

\- 解決不能でも値は保持する

\- 実在性確認はアプリ層責務

\- 比較・保存・転送の最小共通表現として扱う

