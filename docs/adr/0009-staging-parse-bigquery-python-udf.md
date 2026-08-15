# ADR-0009: staging層のパースは BigQuery Python UDF で実装する

## 状態
確定

## 決定
`stg_piyolog__daily_headers` / `stg_piyolog__events` / `stg_piyolog__daily_notes` の3テーブルは、raw の `raw_content` を状態機械でパースする必要がある(ADR-0005)。この状態機械は BigQuery の Managed Python UDF(`CREATE FUNCTION ... LANGUAGE python`)として実装し、dbt の staging モデル(SQL)から呼び出す。dbt は raw → staging → intermediate → marts の全レイヤーを引き続き管理する。

パーサ本体のコードは `src/piyolog/parse.py` に通常の Python モジュールとして置き、GCS 経由で UDF 定義から参照する(コードの二重管理を避ける)。UDF ルーティン自体は `tf/modules/bigquery/` を拡張し `google_bigquery_routine` で Terraform 管理する。

## 根拠

### 検討した選択肢

| 案 | 概要 | 判定 |
|---|---|---|
| A: dbt Python model | BigQuery DataFrames(bigframes)/Dataproc 経由で dbt Python model を実行 | 却下。2026-08時点で dbt-bigquery の Python model は Preview 止まり。BigFrames submission は Vertex AI API / Compute Engine API / Dataform API 等の新規有効化が必要で、個人プロジェクトの「新規インフラを増やさない」方針に反する |
| B: BigQuery JS UDF | 状態機械を JavaScript UDF として実装し SQL から呼ぶ | 却下。ADR-0005 で既に検討・不採用(「JS UDFでも可能だが手続き型処理はPythonが自然」)。加えて Python設計ガイド(モックなし pytest によるビジネスロジックの単体テスト)を満たせない |
| C: 既存 Cloud Run job にパース処理を追加 | raw 取り込みジョブの Python コードを拡張し、BQ の `raw_content` を読んで staging テーブルへ直接書き込む | 不採用。dbt の役割が raw→staging で分断され、overview.md のレイヤー構成(dbtが staging 以降を担う)から外れる |
| **D: BigQuery Python UDF(採用)** | Managed Python UDF (`LANGUAGE python`) を dbt の staging モデルから呼ぶ | 採用。2026-06-22 に GA。新規 GCP サービス不要、既存 Terraform 管理下の BigQuery だけで完結し、dbt の staging レイヤーとしての立ち位置も維持できる |

### GA 状況の確認
BigQuery Managed Python UDF は 2026-06-22 に GA(標準ライブラリ・ループ・正規表現・状態を持つ処理に対応。`packages` オプションで PyPI 依存も追加可能。ランタイムは `python-3.11` のみ、JSON/RANGE/INTERVAL/GEOGRAPHY型は非対応、コンテナは最大 4 vCPU / 16 GiB)。新規インフラ導入前に GA 状況を確認する方針に基づき採用可と判断した。

### デバッグ困難性への対策
BigQuery UDF 実行時のデバッグは BQ 側のプラットフォームに依存するため難しい。この対策として、パーサ本体を BQ に触れない通常の Python 関数として実装し、UDF の `entry_point` はその薄いラッパーに留める。パーサ内部は reducer パターン(`(state, token) -> state` の純粋関数 + `functools.reduce` による fold)で構成し、行単位のトークン化・状態遷移をそれぞれ pytest でテーブル駆動テストする。これにより UDF 本体を BQ 上でテスト・デバッグする必要性を最小化する(詳細は `src/piyolog/parse.py` 実装時のテスト方針として反映)。

## 影響
- `docs/overview.md` §5.2 の照合キー・アーキ図を本ADRに合わせて更新する(child_name を含める修正は別問題として同時に実施。詳細は overview.md 参照)。
- `tf/modules/bigquery/` に UDF ルーティン用リソースを追加する(実装 TODO)。
