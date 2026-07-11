# ぴよログ → BigQuery 取り込み: staging層 実装指示書

## 0. このドキュメントの位置づけ

`piyolog_raw_layer_spec.md` の続き。raw層(`piyolog_raw.export_files`)から staging層
(`piyolog_staging.stg_piyolog__*`)への変換に限定した実装指示書。全体設計は
`overview.md` §5.2、設計判断の根拠は [ADR-0009](adr/0009-bq-python-udf-parsing.md) を参照。

---

## 1. アーキテクチャ(確定事項)

```
piyolog_raw.export_files (source, Cloud Run job が書き込む。この層では変更しない)
   │
   │ dbt モデルが UDF を1行(1ファイル)ずつ呼ぶ
   ▼
[BigQuery Python UDF] parse_piyolog_export(raw_content, child_name, source_year_month)
   RETURNS STRUCT<headers ARRAY<...>, events ARRAY<...>, notes ARRAY<...>>
   │  dbt が dbt/functions/ で管理・デプロイ(dbt Core v1.11+)
   ▼
piyolog_staging (dbt が構築)
   - stg_piyolog__daily_headers
   - stg_piyolog__events
   - stg_piyolog__daily_notes
```

パースは Cloud Run job ではなく BigQuery Python UDF として実装し、dbt/BigQuery に完結させる。
新規 Cloud Run job・新規データセット・新規 env var は発生しない。

---

## 2. UDF: `parse_piyolog_export`

### ファイル

- `dbt/functions/parse_piyolog_export.py`: UDF本体(自己完結・標準ライブラリのみ)。
  `tests/test_parse.py` から直接 import してモックなしでユニットテストできる
  (`pyproject.toml` の `pythonpath = ["dbt/functions"]` により解決)。
- `dbt/functions/parse_piyolog_export.yml`: dbt function リソース定義(引数・戻り値型・
  `entry_point`・`runtime_version`)。

### シグネチャ

```
parse_piyolog_export(raw_content STRING, child_name STRING, source_year_month DATE)
  RETURNS STRUCT<
    headers ARRAY<STRUCT<
      daily_header_id STRING,
      child_name STRING,
      source_year_month DATE,
      log_date DATE,
      child_age_raw STRING
    >>,
    events ARRAY<STRUCT<
      daily_header_id STRING,
      event_seq INT64,
      event_at DATETIME,
      event_type_raw STRING,
      detail_raw STRING
    >>,
    notes ARRAY<STRUCT<
      daily_header_id STRING,
      note_raw STRING
    >>
  >
```

戻り値は JSON ではなく STRUCT(BigQuery Python UDF は JSON 型非対応のため。詳細は
[ADR-0009](adr/0009-bq-python-udf-parsing.md))。`DATE`/`DATETIME` はネイティブ型のまま
Python の `date`/`datetime` オブジェクトとして往復する。

### パース状態機械

`raw_content` を `----------` で日次セクションに分割し、各セクションを
`HEADER → EVENTS → SUMMARY → NOTES` の4状態で走査する(仕様は `overview.md` §5.2 と同一)。

1. **HEADER**: 日付行 `YYYY/M/D(曜)` → `log_date`。名前・年齢行 `名前 (X歳Yか月Z日)` →
   `child_age_raw`(名前部分は関数引数の `child_name` を使うため無視する)。
2. **EVENTS**: `母乳合計` 行に到達するまで。イベント開始行判定は行頭
   `^\d{1,2}:\d{2}\s+`(基本3スペース区切り、まれに1スペースの例外あり)。合致しない
   非空行は直前イベントの `detail_raw` に改行付きで追記。
3. **SUMMARY**: `母乳合計` 行〜`うんち合計` 行。読み飛ばす(BQに保持しない)。
4. **NOTES**: `うんち合計` 行の次行〜セクション末尾。全文を `note_raw` として収集。
   空文字列の場合は `notes` 配列に含めない。

### `daily_header_id`

`{child_name}:{log_date.isoformat()}`(例: `child_a:2026-05-01`)。複数の子供のデータが
1テーブルに集約されても衝突しないサロゲートキー。`events` / `notes` はこの ID のみを
外部キーとして持つ(child_name / log_date を repeat しない)。

### `event_at`

`log_date` とイベント時刻(HH:MM)を合成した DATETIME(現地時刻、タイムゾーンなし)。
`events` を単体で日付フィルタできるようにするための非正規化。

---

## 3. dbt モデル

`dbt/models/staging/stg_piyolog__daily_headers.sql` / `stg_piyolog__events.sql` /
`stg_piyolog__daily_notes.sql` は、いずれも次のパターンで実装する。

```sql
with parsed as (
    select
        {{ function('parse_piyolog_export') }}(raw_content, child_name, source_year_month) as result
    from {{ source('piyolog_raw', 'export_files') }}
)

select
    <field>.*
from parsed, unnest(parsed.result.<headers|events|notes>) as <field>
```

小規模データのため、モデルごとに UDF を再呼び出ししてもコストは無視できる。

`dbt/dbt_project.yml` の `functions: piyolog: +schema: staging` により、UDF はモデルと
同じ `piyolog_staging` データセットに作られる。

---

## 4. テストと品質ゲート

- `dbt/models/staging/_piyolog__staging_models.yml`: `daily_header_id` の `unique`/`not_null`
  (daily_headers, daily_notes)、`event_type_raw` の `not_null` + `accepted_values`
  (severity: warn、`docs/known_event_types.md` の33種別)
- `dbt/tests/assert_stg_piyolog__events_unique_key.sql`: `(daily_header_id, event_seq)` の
  複合一意性を検証する単発テスト(dbt_utils 非依存)
- `tests/test_parse.py`: `parse_piyolog_export.py` のユニットテスト(pytest, モックなし)

---

## 5. 実行方法

```bash
uv sync --extra dev
uv run pytest tests/test_parse.py -v          # UDFロジックのユニットテスト
uv run dbt build --select "resource_type:function stg_piyolog__daily_headers+ stg_piyolog__events+ stg_piyolog__daily_notes+" --project-dir dbt --profiles-dir dbt
```

`dbt build` の実行には BigQuery 認証情報(`GOOGLE_APPLICATION_CREDENTIALS` 等)と
`piyolog_staging` データセットの事前 provision(Terraform、TODO.md 参照)が必要。

---

## 6. 未検証のリスク(実装時に確認する)

- 外部呼び出しを行わない素の Python UDF に Cloud Resource Connection が必要かどうか
- `runtime_version: "3.12"` が BigQuery Python UDF でサポートされない場合は `"3.11"` 等に調整
