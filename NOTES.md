# 作業メモ

## 現状

HaskellベースからPythonベースへの実装切り替えを決定。Haskell資材は削除済み。

## 完了した作業

### Haskell資材の削除
- `piyolog.cabal`, `app/`, `src/`, `test/`, `CHANGELOG.md` を削除
- `.github/workflows/ci.yml` (Haskell CI) を削除
- `.vscode/tasks.json` (cabalビルドタスク) を削除

### devcontainerのPython/uv対応
- `Dockerfile`: `base:ubuntu` + uvバイナリを公式イメージから `COPY --from` で導入
  ```dockerfile
  COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
  ```
- `.devcontainer/install-tools.sh`: Claude Code (バイナリ版) と `uv sync` を実行
- `devcontainer.json`: Python/Pylance/Ruff拡張、postCreateCommand でスクリプト実行
- `.gitignore`: Python用に更新

### pyproject.toml の作成

- `pyproject.toml`: uv管理、hatchlingビルドバックエンド、Python>=3.12
  - 依存: `cryptography`, `httpx`, `PyJWT`
  - dev依存: `pytest`, `pytest-asyncio`
- `uv.lock`: ロックファイルを生成済み (`uv lock`)

### CI の Python 対応

- `.github/workflows/ci.yml`: uv install → ruff lint → pytest

## 次にやること

- Pythonでの実装開始 (`src/piyolog/` 以下)

## 設計ドキュメント

- `docs/gcs-api-design.md`
- `docs/jwt-design.md`
