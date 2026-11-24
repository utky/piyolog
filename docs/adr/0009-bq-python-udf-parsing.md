# ADR-0009: staging層のパースは BigQuery Python UDF で実施し dbt に統合する(ADR-0005 改訂)

## 状態
確定

## 決定
raw の `raw_content` を状態機械でパースする処理は、外部の Cloud Run job ではなく
**BigQuery Managed Python UDF**(`parse_piyolog_export`)として実装し、dbt の `functions/` リソースで
管理する。dbt の `stg_piyolog__daily_headers` / `stg_piyolog__events` / `stg_piyolog__daily_notes`
モデルがこの UDF を呼び出し、戻り値の `STRUCT` を `UNNEST` して行に展開する。

- UDF 本体は自己完結した1ファイル `dbt/functions/parse_piyolog_export.py`(標準ライブラリのみ)に書き、
  dbt がそのまま UDF 本体としてデプロイする。pytest は `pyproject.toml` の `pythonpath` 経由で
  同じファイルを直接 import するため、コードの二重管理は発生しない
- `runtime_version` は `"3.11"`(dbt が `python-3.11` に変換)。BigQuery Python UDF が
  サポートするランタイムは `python-3.11` のみのため、UDF 本体は 3.11 互換の構文で書く
- パーサ内部は reducer + fold パターンで構成する(後述「デバッグ困難性への対策」)

## 根拠
ADR-0005 は「状態を持つ逐次処理は純粋な SQL では表現できない」という前提から、パース処理を
BQ の外(Cloud Run job)に出す決定をした。この前提自体は正しいが、**BigQuery Python UDF は
関数本体が通常の Python コードであり、1行の `raw_content` を処理する範囲内であれば状態を持つ
逐次処理を問題なく書ける**。つまり「BQ完結を断念する」という結論部分は、UDF という選択肢を
考慮していなかったための誤りだった。

### 検討した選択肢

| 案 | 概要 | 判定 |
|---|---|---|
| A: dbt Python model | BigQuery DataFrames(bigframes)/Dataproc 経由で dbt Python model を実行 | 却下。2026-08時点で dbt-bigquery の Python model は Preview 止まり。BigFrames submission は Vertex AI API / Compute Engine API / Dataform API 等の新規有効化が必要で、個人プロジェクトの「新規インフラを増やさない」方針に反する |
| B: BigQuery JS UDF | 状態機械を JavaScript UDF として実装し SQL から呼ぶ | 却下。ADR-0005 で既に検討・不採用(手続き型処理は Python が自然)。加えて Python設計ガイド(モックなし pytest によるビジネスロジックの単体テスト)を満たせない |
| C: 既存 Cloud Run job にパース処理を追加 | raw 取り込みジョブを拡張し、staging テーブルへ直接書き込む | 却下。後述 |
| D: Python UDF を Terraform で管理 | パーサを `src/piyolog/parse.py` に置き、GCS にアップロードして `google_bigquery_routine` から参照する | 却下。GCS バケット・アップロード手順・Terraform リソースが増える。dbt functions でも同一ファイルを pytest とデプロイの両方に使えるため、二重管理回避という利点が D 固有ではない |
| **E: Python UDF を dbt functions で管理(採用)** | `dbt/functions/` に `.py` + `.yml` を置き、`{{ function() }}` で staging モデルから呼ぶ | 採用。新規 GCP サービス・新規データセット・新規 env var が不要。dbt Core v1.11 で Python UDF サポートが GA |

案 C を採用しなかった理由:

- Python job が書き込む先のデータセットを新設すると、既存 `piyolog_raw` との役割の違いが
  分かりにくいインフラが増える
- 既存の `piyolog_staging` を再利用すると、`dbt_project.yml` が既に
  `models.piyolog.staging.+schema: staging` として「dbt が構築するモデルの器」と
  定義しているため、そこに dbt が関与しないテーブルを置くと紛らわしい
- dbt の役割が raw→staging で分断され、overview.md のレイヤー構成(dbt が staging 以降を担う)から外れる

UDF 方式では、dbt が `stg_piyolog__*` を実際に構築するため、`stg_` プレフィックス
([dbt命名規約](https://docs.getdbt.com/blog/stakeholder-friendly-model-names))が文字通り正しい。

### GA 状況の確認
BigQuery Managed Python UDF は 2026-06-22 に GA(標準ライブラリ・ループ・正規表現・状態を持つ処理に対応。
`packages` オプションで PyPI 依存も追加可能。ランタイムは `python-3.11` のみ、JSON/RANGE/INTERVAL/GEOGRAPHY 型は
非対応、一時関数・マテリアライズドビューでの利用は不可)。新規インフラ導入前に GA 状況を確認する方針に基づき採用可と判断した。

### デバッグ困難性への対策
BigQuery UDF 実行時のデバッグは BQ 側のプラットフォームに依存するため難しい。この対策として、
UDF の `entry_point`(`parse_piyolog_export`)は薄いラッパーに留め、パーサ本体は BQ に触れない純粋関数で構成する。

1. `classify_line(line) -> LineToken`: 行 → 構造化トークン(行レベル)
2. `step(state, token) -> ParseState`: 状態遷移の reducer(イミュータブル dataclass。ファイル末尾は
   `EndOfFile` 番兵トークンで最終セクションを確定)
3. `parse_export_content(...)`: `functools.reduce(step, tokenize(raw_content), initial_state)` による畳み込み

`classify_line` / `step` を pytest でテーブル駆動テストすることで、UDF 本体を BQ 上でテスト・デバッグする必要性を最小化する。

## 戻り値の型: STRUCT(JSON は不使用)

BigQuery Python UDF は JSON 型非対応のため、`STRUCT` / `ARRAY` を使う。Python の `dict`/`list` が
そのままマッピングされ、`DATE`/`DATETIME` もネイティブ型で往復できる。UDF は `headers` / `events` /
`notes` を持つネストした `STRUCT`(3テーブルの構造をそのまま内包する型)を返す。

## トレードオフ

- 素の Python UDF(外部呼び出しなし)に Cloud Resource Connection が必要かどうかは、初回 `dbt build` で確認する
- UDF 本体は `requires-python = ">=3.12"` のプロジェクト内にあるが、BigQuery 上では 3.11 で動くため、
  3.12 以降の構文(`type` 文、PEP 695 ジェネリクス等)を使わない
- 未知種別の検知(方針P)は UDF 内では行わず、`stg_piyolog__events.event_type_raw` への
  dbt `accepted_values` スキーマテスト(severity: warn)に委ねる。`dbt build`/`dbt test` の実行結果自体が品質ゲートになる
