# ADR-0009: staging層のパースは BigQuery Python UDF で実施し dbt に統合する(ADR-0005 改訂)

## 状態
確定

## 決定
raw の `raw_content` を状態機械でパースする処理は、外部の Cloud Run job ではなく
**BigQuery Python UDF**(`parse_piyolog_export`)として実装し、dbt の `functions/` リソースで
管理する。dbt の `stg_piyolog__daily_headers` / `stg_piyolog__events` / `stg_piyolog__daily_notes`
モデルがこの UDF を呼び出し、戻り値の `STRUCT` を `UNNEST` して行に展開する。

## 根拠
ADR-0005 は「状態を持つ逐次処理は純粋な SQL では表現できない」という前提から、パース処理を
BQ の外(Cloud Run job)に出す決定をした。この前提自体は正しいが、**BigQuery Python UDF
(2025年GA)は関数本体が通常の Python コードであり、1行の `raw_content` を処理する範囲内で
あれば状態を持つ逐次処理を問題なく書ける**。つまり「BQ完結を断念する」という結論部分は、
UDF という選択肢を考慮していなかったための誤りだった。

検討の過程で、Cloud Run job が staging テーブルへ直接書き込む案(実装当初の方向性)も
具体化したが、以下の理由で採用しなかった:

- Python job が書き込む先のデータセットを新設すると、既存 `piyolog_raw` との役割の違いが
  分かりにくいインフラが増える
- 既存の `piyolog_staging` データセットを再利用すると、`dbt_project.yml` が既に
  `models.piyolog.staging.+schema: staging` として「dbt が構築するモデルの器」と
  定義しているため、そこに dbt が関与しないテーブルを置くと「データセット名」
  「dbtのスキーマ生成規則」「dbt source名」が同じ文字列に重なり紛らわしい

UDF 方式はこの問題自体を発生させない。理由は以下の通り。

- パースが dbt/BigQuery に完結し、Cloud Run job・新規データセット・新規 env var が不要
- dbt が `stg_piyolog__*` を実際に構築するため、`stg_` プレフィックス([dbt命名規約](https://docs.getdbt.com/blog/stakeholder-friendly-model-names))が文字通り正しい
- dbt は `functions/` ディレクトリで UDF を第一級リソースとして管理できる
  (dbt Core v1.11 で Python UDF サポートが GA)
- パースの純粋ロジックは1つの自己完結した `.py` ファイル(`dbt/functions/parse_piyolog_export.py`)
  に書け、それをそのまま UDF 本体としてデプロイしつつ、pytest でモックなしに直接
  ユニットテストできる

## 戻り値の型: STRUCT(JSON は不使用)

当初 `RETURNS JSON` を検討したが、**BigQuery Python UDF は JSON 型を非対応**
(JSON, RANGE, INTERVAL, GEOGRAPHY はサポート外)。`STRUCT` / `ARRAY` は正式サポートされ、
Python の `dict`/`list` がそのままマッピングされ、`DATE`/`DATETIME` もネイティブ型で
往復できる。そのため UDF は `headers` / `events` / `notes` を持つネストした `STRUCT`
(3テーブルの構造をそのまま内包する型)を返す。

## トレードオフ

- BigQuery Python UDF は比較的新しい機能であり、素の Python UDF(外部呼び出しなし)に
  Cloud Resource Connection が必要かどうか等、実装時に確認すべき細部が残る
- 未知種別の検知(方針P)は UDF 内では行わず、`stg_piyolog__events.event_type_raw` への
  dbt `accepted_values` スキーマテスト(severity: warn)に委ねる。これにより
  `dbt build`/`dbt test` の実行結果自体が品質ゲートになる
