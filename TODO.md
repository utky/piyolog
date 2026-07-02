# TODO

ロードマップと設計ドキュメント (`docs/overview.md`) に基づくタスク一覧。

---

## フェーズ1: raw 層 ✅ 完了

- [x] Drive API 読み取り + BQ raw テーブル (Cloud Run job, Python)

---

## デプロイ: raw 層 (Terraform IaC)

参考実装: [utky/preschool-agent tf/](https://github.com/utky/preschool-agent/tree/18faa675a85f3271fa7307d52d98ba8392fd4c75/tf)
(モジュール構成: `tf/modules/<concern>/` + `tf/environments/<env>/`、GCS バックエンドで state 管理)

### 設計 (確定)

- GCP プロジェクト: [utky/lofilab](https://github.com/utky/lofilab) が管理する既存プロジェクト `lofilab` を再利用する。`preschool-agent` も同プロジェクトを使っている。lofilab の `modules/service_api` には bigquery/run/cloudscheduler/iam を含む API 一覧が定義されているが、実際に `terraform apply` 済みかは lofilab 側のリポジトリ外からは確認できないため、`terraform apply` 時に API 未有効化エラーが出た場合は lofilab 側で `service_api` を適用し直す (このリポジトリの tf では API 有効化を行わない)
- コンテナイメージ: lofilab 共有 Artifact Registry `utky-applications` を再利用 (`asia-northeast1-docker.pkg.dev/lofilab/utky-applications/piyolog-importer`)。専用リポジトリは作らない
- ビルド/push: GitHub Actions CI (`.github/workflows/deploy.yml`) で WIF 経由で自動 build/push する。Cloud Run Jobs は `:latest` push だけでは新イメージを再取得しないため、CI内で `gcloud run jobs update --image` による明示的な再デプロイも行う (Terraform apply は経由しない。Job自体の作成は最初の `terraform apply` が前提)
  - lofilab 側の対応は完了済み: [utky/lofilab@b3961f1](https://github.com/utky/lofilab/commit/b3961f17ba0847dc2024d04e0be7c567b30d3364) (main ブランチ) で `github_repos` 変数の default に `"utky/piyolog"` が追加され、`tfvars` 運用自体も廃止された (secret を含まない値はコード管理に統一)。残作業はこのコードを lofilab 側で `terraform apply` して WIF provider/SA を実体化し、その出力値を piyolog 側の GitHub Actions repository variables に設定するだけ (下記「残りの作業」参照)
- Terraform ディレクトリ構成: `tf/modules/{bigquery,cloud_run_job,scheduler}/` + `tf/environments/production/` (実装済み)
- tfstate バックエンド: GCS バケット `lofilab-piyolog-tfstate` (preschool-agent の命名規則 `lofilab-<app>-tfstate` を踏襲)。バケット自体は Terraform 管理外、手動 bootstrap が前提 (参考実装と同様)
- raw 層ジョブ用 SA の権限: `roles/bigquery.dataEditor` + `roles/bigquery.jobUser` (preschool-agent の dbt SA 構成を踏襲)。Drive アクセスは IAM では付与できないため、SA のメールアドレスを Drive フォルダ側で手動共有する運用とする
- 環境変数: `BQ_PROJECT_ID` / `BQ_DATASET_ID` / `BQ_TABLE_ID` / `DRIVE_CHILD_FOLDERS` / `LOG_LEVEL` を `google_cloud_run_v2_job` に渡す。`DRIVE_CHILD_FOLDERS` は JSON 文字列の `sensitive` 変数として tfvars で管理 (リポジトリにはコミットしない。`terraform.tfvars.example` を参照用に用意)
- BigQuery データセット/テーブル: Terraform (`tf/modules/bigquery/`) で事前 provision する。job 側 (`bq.py`) はテーブル存在確認のみで作成は行わない
- 定期実行: 日次1回 (`0 6 * * * Asia/Tokyo`) の Cloud Scheduler → Cloud Run Jobs API (`:run` エンドポイント) 直接呼び出し。単一ジョブで引数オーバーライドが不要なため Cloud Workflows は使わず、Scheduler 専用 SA に `roles/run.invoker` を付与するだけで足りる

### 実装 (完了)

- [x] `tf/environments/production/{main,variables,outputs}.tf` + `terraform.tfvars.example`
- [x] `tf/modules/bigquery/` (データセット + `export_files` テーブル定義。`bq.py` の `SCHEMA` と一致確認済み)
- [x] `tf/modules/cloud_run_job/` (サービスアカウント, IAM, `google_cloud_run_v2_job`)
- [x] `tf/modules/scheduler/` (日次 Cloud Scheduler → Cloud Run Jobs API 直接呼び出し用 SA と IAM)
- [x] `.github/workflows/deploy.yml` (WIF 経由でイメージを build/push する CI)

### 残りの作業 (適用・運用)

- [x] (ユーザー作業) GCS バケット `lofilab-piyolog-tfstate` を手動作成する
- [x] (ユーザー作業) lofilab を `terraform apply` し、`github_repos` の default 値 (`"utky/piyolog"` 追加済み, [b3961f1](https://github.com/utky/lofilab/commit/b3961f17ba0847dc2024d04e0be7c567b30d3364)) を反映させて WIF provider/SA を実体化する
- [x] (ユーザー作業) lofilab apply 後の出力 (`workload_identity_provider` / `service_account_email`) を、この piyolog リポジトリの GitHub Actions repository variables (`WORKLOAD_IDENTITY_PROVIDER` / `GCP_SERVICE_ACCOUNT_EMAIL`) に設定する
- [x] (ユーザー作業) `tf/environments/production/terraform.tfvars` を `terraform.tfvars.example` を参考に作成する (`drive_child_folders` を含む。コミットしない)
- [x] `terraform init` → `terraform plan` → `terraform apply` を実行し、BQ データセット/テーブル・Cloud Run job・Scheduler を作成する
- [x] CI を1回実行してイメージを push する (または手動 `docker build && push`) (`Build and Push Image` run #28609790903, `asia-northeast1-docker.pkg.dev/lofilab/utky-applications/piyolog-importer` に push 済み)
- [x] (ユーザー作業) 取り込みジョブ用 SA (`importer_service_account_email` output) を Drive の子供別フォルダに共有設定する (親フォルダ経由で共有)
- [x] Cloud Scheduler を手動トリガーし、Cloud Run job が実際に raw 層への取り込みを完走することを確認する (2026-07-02, execution `piyolog-importer-kcggq`, 穂55件/慧12件を `piyolog_raw.export_files` に取り込み完了。なお lofilab 側で Drive API が無効化されていたため一度失敗し、有効化後に再実行して成功)
- [ ] 上記構成をもとに Google Cloud の費用を見積もる (Cloud Run job 実行時間課金, BigQuery ストレージ/クエリ, Artifact Registry ストレージ, Cloud Scheduler 等)

---

## 事前準備 (ユーザー作業)

- [ ] Drive 上のぴよログファイルを子供別サブフォルダへ移動
  - 現状: 単一フォルダ `1BDMCTkCaFEbskGeIGKDzWuUdsb86ME7R` に直置き
  - 移動先構成: `ぴよログ/<child_name>/【ぴよログ】YYYY年M月.txt`

---

## フェーズ2: 種別棚卸し

- [ ] BQ の `raw_content` から全期間・全子供の種別を抽出するクエリ/スクリプトを書く
- [ ] 抽出した種別の和集合を確定し、既知種別リスト (`docs/known_event_types.md` 等) として文書化する
- [ ] `overview.md` §5.3 の暫定種別グループを確定版で更新する

---

## フェーズ3: staging (仕様確定・実装 TODO)

目標テーブル: `stg_daily_header` / `stg_events` / `stg_daily_notes`

- [ ] dbt プロジェクトを初期化する (`dbt init`)
- [ ] `stg_daily_header` モデルを実装する (粒度: 日次1レコード)
- [ ] `stg_events` モデルを実装する (粒度: イベント1レコード)
  - 状態機械パース (HEADER → EVENTS → SUMMARY → NOTES)
  - イベント開始行判定: `^\d{1,2}:\d{2}\t`
  - EVENTS 終了マーカー: `母乳合計`
  - SUMMARY 終了マーカー: `うんち合計`
  - 複数行詳細テキストの `detail_raw` への追記
- [ ] `stg_daily_notes` モデルを実装する (粒度: 日次1レコード)
- [ ] 照合キー `(source_year_month, log_date)` のユニーク制約テストを追加する
- [ ] 未知種別が出た場合に警告/エラーで検知する仕組みを実装する (方針P)

---

## フェーズ4: intermediate - 種別ごとテーブル (スキーマ設計 TODO)

- [ ] 確定した種別リストをもとに種別ごとテーブルのスキーマを設計する
- [ ] `stg_events` から種別ごとに分割する dbt モデルを実装する
  - 数値/量型: 体温, のみもの, ミルク, 搾乳/搾母乳
  - 状態型: 起きる, 寝る, おしっこ, うんち
  - 授乳型: 母乳 (複数フォーマット対応)
  - 自由記述型: 離乳食, ごはん, おやつ, さんぽ, 病院, 幼稚園, その他
  - トレーニング型: マイオブレース (🔴△❌)
  - ルーティン型: 生活習慣, スキンケア, くすり, ミルトン交換
  - 発達記録型: できた

---

## フェーズ5: intermediate - 区間データ・enrich (設計 TODO)

- [ ] `sleep_intervals` モデルを設計・実装する
  - `寝る` → `起きる` のペアリングで睡眠区間を構築 (方針Y: `起きる` の継続時間を duration として採用)
- [ ] enrich モデルを設計する
  - 年齢の構造化 (child_age_raw → 歳/か月/日の数値)
  - 曜日・時間帯の付与

---

## フェーズ6: marts (用途確定後)

- [ ] 用途を確定する (候補: 月次レポート生成 / 健康記録ダッシュボード / Obsidian 日次ノート連携)
- [ ] 用途特化マートを実装する

---

## フェーズ7: dbt 整備 (並行)

- [ ] dbt プロジェクト構成・命名規則を決める (`docs/dbt_convention.md` 等)
- [ ] 各モデルに dbt テストを追加する (not_null, unique, accepted_values)
- [ ] CI でテストを自動実行する仕組みを整備する

---

## 将来検討 (バックログ)

- [ ] `daily_notes` の全文検索: データ量増加時に BQ SEARCH INDEX の採用を再検討する
- [ ] 病院記録やイベント詳細を含めた横断検索の要否を評価する
