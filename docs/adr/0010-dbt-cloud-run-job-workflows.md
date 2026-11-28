# ADR-0010: dbt は Cloud Run job で実行し、取り込みジョブとの順序を Workflows で制御する

## 状態
確定(2026-11-27 本番 apply・Workflow 実行で動作確認済み)

## 決定

- `dbt build` を専用の Cloud Run job **`piyolog-dbt`** として実行する。イメージは importer とは別の
  `piyolog-dbt`(`Dockerfile.dbt`、`[dependency-groups] dbt` のみをインストール)。
- 日次パイプラインを Cloud Workflows **`piyolog-daily`** で定義し、Cloud Scheduler(毎日 06:00 JST)から起動する。
  1. `piyolog-importer`(Drive → raw)を実行し、完了を待つ
  2. `piyolog-dbt`(staging / intermediate / marts の構築 + dbt test)を実行し、完了を待つ
- importer が失敗しても dbt は実行し、最後に importer のエラーを再送出して Workflow 実行を失敗にする。
- インフラは既存どおり Terraform(OpenTofu)で管理し、**apply はローカルから手動**で行う。
  イメージの build/push と `gcloud run jobs update` は既存の `deploy.yml` に dbt イメージを追加する。

## 根拠

### dbt の実行場所

| 案 | 判定 |
|---|---|
| ローカルから手動実行 | 初回デプロイ確認のみ。定期実行・table の更新には使えない |
| GitHub Actions(main マージ時 / スケジュール) | 却下。GitHub Actions の WIF SA に BigQuery のデータ編集権限を新たに付与する必要があり、権限の管理場所が GCP と GitHub に分散する |
| **Cloud Run job(採用)** | importer と同じ構成(Terraform モジュール・Artifact Registry・`deploy.yml`)を踏襲でき、権限は GCP 側の専用 SA に閉じる。今後 marts で table が増えても日次で更新できる |

staging / intermediate は現状 view なので、モデル変更時以外は dbt を毎日実行する必然性はない。
それでも日次で実行するのは、(1) `dbt test` を品質ゲートとして毎日回す(未知種別・重複の検知。
実際に初回 `dbt build` で raw の重複と未知種別を検知した)、(2) marts の table 更新に備える、ため。

### ジョブ間の順序制御

| 案 | 判定 |
|---|---|
| 同一 job 内で importer → dbt を連続実行 | 却下。1イメージに両方の依存・1つの SA に Drive と dbt の両方の権限が混在する |
| 別 job + Scheduler の時刻ずらし | 却下。順序が時刻でしか保証されず、後続ステップ(marts 以降の処理)が増えるほど脆くなる |
| **別 job + Cloud Workflows(採用)** | `googleapis.run.v2.projects.locations.jobs.run` コネクタがジョブ実行の完了を待つため、依存を明示できる。日次数ステップなら無料枠内。後続処理もステップ追加で拡張できる |

raw 層デプロイ時(PR #3)に「Cloud Workflows は使わない」としたのは、**単一ジョブ・引数オーバーライド不要**という
前提での判断だった(`tf/modules/scheduler` のコメント)。ジョブが2つになり順序依存が生じたため、その前提は成り立たない。

### importer 失敗時も dbt を実行する理由

raw は `(child_name, source_year_month)` 単位の洗い替えで常に整合した状態にあり、importer が途中で
失敗しても(例: 同月複数ファイルの検知で SystemExit)、dbt は前回までの raw から正しく再構築できる。
dbt test も毎日回したいので dbt はスキップしない。importer の失敗は Workflow 実行の失敗として残す。

## 権限(最小権限)

| SA | 権限 |
|---|---|
| `piyolog-dbt-sa` | project: `roles/bigquery.jobUser` / raw データセット: `roles/bigquery.dataViewer` / staging・intermediate・marts データセット: `roles/bigquery.dataEditor`(view・table・UDF の作成/置換) |
| `piyolog-workflow-sa` | 各 job: `roles/run.invoker`(`run.jobs.run`) / project: `roles/run.viewer`(完了待ちのポーリング) / project: `roles/logging.logWriter` |
| `piyolog-scheduler-sa` | project: `roles/workflows.invoker`(旧構成の importer job への `roles/run.invoker` は廃止) |

公式チュートリアルは Workflow の SA に `roles/run.admin` を付与しているが、job 単位の invoker + project の viewer で
足りることを初回 apply 後の Workflow 実行で確認した(2026-11-27)。

## トレードオフ・既知の注意点

- dbt build のたびに Python UDF を `CREATE OR REPLACE` するため、BigQuery 側で UDF のコンテナイメージ再作成が走る
  (外部依存なしで通常1分未満)。実行時間が問題になれば、日次実行は `--exclude resource_type:function` にし、
  UDF のデプロイはモデル変更時に限定する。
- 初回は「main マージ → CI が `piyolog-dbt` イメージを push → ローカルで `tofu apply`」の順にする
  (Cloud Run job の作成時にイメージが存在している必要がある)。
