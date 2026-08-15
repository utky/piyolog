# dbt モデル命名・設計原則

このプロジェクト（ぴよログ → BigQuery）における dbt の命名規則と設計方針。

## レイヤー構成と BigQuery データセット

| レイヤー | BQ データセット | モデルプレフィックス | 内容 |
|---|---|---|---|
| raw | `piyolog_raw` | なし（source） | Cloud Run job が書き込む生テキスト。dbt の管理外 |
| staging | `piyolog_staging` | `stg_` | raw を行レベルにパース。なるべく生データを残す |
| intermediate | `piyolog_intermediate` | `int_` | 種別ごと分割・区間データ・enrich |
| marts | `piyolog_marts` | `fct_` / `dim_` | 用途特化マート |

## モデル命名規則

```
<prefix>_<source>__<entity>[__<context>]
```

- `stg_piyolog__export_files` — raw の export_files を行レベルにパースしたステージング
- `stg_piyolog__events` — イベント行 1 レコード
- `stg_piyolog__daily_headers` — 日次ヘッダー 1 レコード
- `stg_piyolog__daily_notes` — 日次メモ 1 レコード
- `int_piyolog__sleep_intervals` — 寝る→起きるのペアリングで区間化
- `int_piyolog__events_temperature` — 体温イベントを構造化
- `fct_piyolog__sleep` — 睡眠マート

## raw テーブル（source）

- BQ テーブル: `piyolog_raw.export_files`
- dbt source 参照: `{{ source('piyolog_raw', 'export_files') }}`
- スキーマ: `child_name`, `source_year_month`(DATE 月初日), `file_name`, `drive_file_id`, `raw_content`, `loaded_at`
- 洗い替え単位: `(child_name, source_year_month)`

## staging 設計方針

- パース本体は BigQuery Managed Python UDF として実装し、dbt の staging モデル（SQL）から呼び出す（[ADR-0009](../../docs/adr/0009-staging-parse-bigquery-python-udf.md)）。UDF コードは `src/piyolog/parse.py` に通常の Python モジュールとして置き、pytest でユニットテストする
- パーサ内部は reducer + fold パターンで構成する: `classify_line(line) -> LineToken`（行レベル）→ `step(state, token) -> state`（状態遷移 reducer）→ `functools.reduce` によるファイル単位の畳み込み。詳細は `docs/overview.md` §5.2「実装パターン」参照
- パース状態機械: `HEADER → EVENTS → SUMMARY → NOTES`
- イベント開始行判定: `^\d{1,2}:\d{2}\s+`(半角スペース区切り。タブは実データに存在しない)
- EVENTS 終了マーカー: `母乳合計` で始まる行
- SUMMARY（`母乳合計`〜`うんち合計`）は BQ に保持しない
- NOTES は `うんち合計` 行の次行〜セクション末尾
- 年齢はイベント行に持たせず header と結合（正規化）。`child_name` は各テーブルの主キーの一部として保持する（同一年月に複数の子供のファイルが併存するため）
- 照合キー: `(child_name, source_year_month, log_date)`(events はさらに `event_seq`)

## intermediate 設計方針

- 既知種別を固定定義し、未知種別は警告で検知（方針 P）
- 睡眠 staging は生のまま 1 行（方針 X）、区間化は intermediate で（方針 Y）
- `起きる` に付随する継続時間を duration として信頼する

## 参考

- 命名規則の出典: https://docs.getdbt.com/blog/stakeholder-friendly-model-names
- 全体設計: `docs/overview.md`
- raw 層仕様: `docs/piyolog_raw_layer_spec.md`
