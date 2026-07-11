# dbt モデル命名・設計原則

このプロジェクト（ぴよログ → BigQuery）における dbt の命名規則と設計方針。

## レイヤー構成と BigQuery データセット

| レイヤー | BQ データセット | モデルプレフィックス | 内容 |
|---|---|---|---|
| raw | `piyolog_raw` | なし（source） | Cloud Run job が書き込む生テキスト。dbt の管理外 |
| staging | `piyolog_staging` | `stg_` | raw を BigQuery Python UDF で状態機械パースし行レベル化。なるべく生データを残す |
| intermediate | `piyolog_intermediate` | `int_` | 種別ごと分割・区間データ・enrich |
| marts | `piyolog_marts` | `fct_` / `dim_` | 用途特化マート |

staging は dbt SQL モデルが raw を直接パースするのではなく、`parse_piyolog_export`
という **BigQuery Python UDF**(`dbt/functions/`)を呼び出し、その戻り値(STRUCT)を
`UNNEST` して行に展開する構成になっている（[ADR-0009](../../../docs/adr/0009-bq-python-udf-parsing.md)）。

## モデル命名規則

```
<prefix>_<source>__<entity>[__<context>]
```

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

## functions（BigQuery Python UDF）

- `dbt/functions/<name>.py` + `dbt/functions/<name>.yml` の対で管理する
  (`function-paths: ["functions"]`、dbt Core v1.11+)
- `.py` ファイルは自己完結（標準ライブラリのみ）にする。BQ Python UDF は関数本体を
  単一ファイルとしてデプロイするため、`src/piyolog` パッケージへは依存できない
- 同じ `.py` ファイルを `tests/` から直接 import してモックなしでユニットテストする
  (`pyproject.toml` の `pythonpath` でパス解決)
- モデルからは `{{ function('<name>') }}(...)` で呼び出す
- 戻り値の複雑な型は `STRUCT`/`ARRAY` を使う。BigQuery Python UDF は `JSON` 型非対応

## staging 設計方針

- パース状態機械: `HEADER → EVENTS → SUMMARY → NOTES`(UDF `parse_piyolog_export` 内で実装)
- イベント開始行判定: `^\d{1,2}:\d{2}\s+`(半角スペース区切り。タブは実データに存在しない)
- EVENTS 終了マーカー: `母乳合計` で始まる行
- SUMMARY（`母乳合計`〜`うんち合計`）は BQ に保持しない
- NOTES は `うんち合計` 行の次行〜セクション末尾
- `child_name` / 年齢はイベント行に持たせず header と結合（正規化）
- 照合キー: `daily_header_id`(`{child_name}:{log_date}` サロゲートキー)。events は
  `(daily_header_id, event_seq)`。複数の子供のデータが1テーブルに集約されるため
  `(source_year_month, log_date)` だけでは一意にならない点に注意
- `events.event_at` は `log_date` + イベント時刻を合成した DATETIME（単体で日付フィルタできるようにするための非正規化）
- 未知種別の検知（方針 P）は UDF ではなく `event_type_raw` への dbt `accepted_values`
  テスト（severity: warn）で行う

## intermediate 設計方針

- 既知種別を固定定義し、未知種別は警告で検知（方針 P）
- 睡眠 staging は生のまま 1 行（方針 X）、区間化は intermediate で（方針 Y）
- `起きる` に付随する継続時間を duration として信頼する

## 参考

- 命名規則の出典: https://docs.getdbt.com/blog/stakeholder-friendly-model-names
- 全体設計: `docs/overview.md`
- raw 層仕様: `docs/piyolog_raw_layer_spec.md`
- staging 層仕様: `docs/piyolog_staging_layer_spec.md`
