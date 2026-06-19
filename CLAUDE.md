# CLAUDE.md

ぴよログ育児記録 → BigQuery データ基盤プロジェクト。個人家庭内用途。

---

## 開発環境

パッケージ管理は `uv`。

```bash
uv sync --extra dev          # 依存インストール
uv run ruff check .          # lint
uv run ruff format .         # フォーマット
uv run pytest --tb=short     # テスト
uv run pytest tests/test_drive.py::test_xxx -v  # 単一テスト
uv run python -m piyolog.main  # ジョブ実行(要環境変数)
```

Docker イメージビルド:

```bash
docker build -t piyolog .
```

---

## 必須環境変数 (ジョブ実行時)

| 変数 | 内容 |
|---|---|
| `BQ_PROJECT_ID` | Google Cloud プロジェクト ID |
| `BQ_DATASET_ID` | BigQuery データセット ID (default: `piyolog_raw`) |
| `BQ_TABLE_ID` | BigQuery テーブル ID (default: `export_files`) |
| `DRIVE_CHILD_FOLDERS` | `{"child_name": "folder_id"}` の JSON |
| `LOG_LEVEL` | ログレベル (default: `INFO`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | サービスアカウント JSON パス (GCP上では不要) |

---

## アーキテクチャ

```
[スマホ] ぴよログ月次エクスポート → Google Drive (子供別フォルダ)
   ↓ Drive API
[Cloud Run job] Python バッチ (src/piyolog/)
   ↓
[BigQuery: raw]   export_files テーブル (1ファイル1レコード)
   ↓ dbt (未実装)
[BigQuery: staging / intermediate / marts]
```

詳細は `docs/overview.md` を参照。設計判断の根拠は `docs/adr/` に個別 ADR として記録している。

---

## コーディング規約

- **言語**: Python 3.12+
- **Lint/Format**: ruff (line-length=100, rules: E/F/I)
- **型ヒント**: 関数シグネチャには必ず付ける
- **ログ**: `logging` モジュール + JSON フォーマッタ。`extra={}` で構造化フィールドを渡す。`print()` は使わない
- **テスト**: pytest。外部 API (Drive/BQ) は `pytest-mock` でモックする
---

## Python設計ガイド

- 関数型プログラミングの原則に従う
    - I/O や副作用と伴う手続きとビジネスロジックの純粋関数をレイヤとして分離する
    - ビジネスロジックはイミュータブルなデータモデルと関数 (または静的メソッド) で構成する
    - ビジネスロジックは純粋関数であるためモックを使わずにユニットテストを記述する

---

## Git ワークフロー

- 作業はフィーチャーブランチ → Pull Request → レビュー → main へマージ
- レビューコメントには追加コミットで対応する (force-push での書き直しはしない)

---

## 設計原則

1. **raw 層に全文保持**: Drive ファイルのテキストをそのまま BQ に入れる。パースロジック改善時は Drive に再アクセスせず raw から再パースできる (ADR-0003)。
2. **洗い替え単位は `(child_name, source_year_month)`**: 月次ファイルの再エクスポート・訂正に対応。job 再実行は常に安全 (冪等)。
3. **子供の区別は Drive フォルダで行う**: ファイル名に子供名は含まれないため、フォルダ階層で分離 (ADR-0007)。
4. **パースは Python**: BQ SQL 完結は困難なため、状態機械パースは Python で実施 (ADR-0005)。
5. **未知種別は警告で検知**: 既知種別を固定定義し、アプリ更新で記録項目が増えた場合に気づける品質ゲートを設ける (方針P)。
6. **日次集計フッターは BQ に保存しない**: `母乳合計` 〜 `うんち合計` の集計ブロックは読み飛ばし、都度 SQL で集計する (ADR-0006)。
7. **データ量は小さい**: 数年分でも数 MB 規模。過度な最適化より可読性と反復しやすさを優先する。

---

## ドキュメント

| ファイル | 内容 |
|---|---|
| `docs/overview.md` | 全体設計・レイヤー構成・ロードマップ |
| `docs/piyolog_raw_layer_spec.md` | raw 層の実装仕様 |
| `docs/adr/` | 設計判断の ADR |
| `TODO.md` | 実装タスク一覧 |
