# Contributing

1. Python 3.10--3.13で開発する。
2. 実装は `src/agent_taskstate/` に集約し、`src.cli`へ実装を追加しない。
3. 振る舞い変更では tests、schema/migration、docsを同時に更新する。
4. typed_refは4セグメントcanonical、state変更は履歴サービス経由とする。
5. `uv run pytest -q`、Ruff、mypy、wheel buildを実行し、生成物をtrackedに残さない。
