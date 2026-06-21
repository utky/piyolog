# TODO

ロードマップと設計ドキュメント (`docs/overview.md`) に基づくタスク一覧。

---

## フェーズ1: raw 層 ✅ 完了

- [x] Drive API 読み取り + BQ raw テーブル (Cloud Run job, Python)

---

## デプロイ: raw 層 (Terraform IaC, 未着手)

参考実装: [utky/preschool-agent tf/](https://github.com/utky/preschool-agent/tree/18faa675a85f3271fa7307d52d98ba8392fd4c75/tf)
(モジュール構成: `tf/modules/<concern>/` + `tf/environments/<env>/`、GCS バックエンドで state 管理)

### 設計

- [ ] 必要なリソースを洗い出す (サービスアカウント, Cloud Run job, Artifact Registry, BQ データセット/テーブル, Cloud Scheduler, API 有効化など)。以降のタスクはこの洗い出し結果を前提に進める
- [ ] [utky/lofilab](https://github.com/utky/lofilab) の共有リソース定義を確認し、再利用できるものを洗い出す
  - Artifact Registry リポジトリ (`modules/repository`, 共有リポジトリ `utky-applications`)
  - GitHub Actions 用 Workload Identity Federation + デプロイ用 SA (`modules/wif`)
  - 必要 API の有効化 (`modules/service_api`)
  - → raw 層専用にこれらを作り直す必要があるか、lofilab 側に追加・参照する形にするかを決める
- [ ] Terraform ディレクトリ構成を決める (`tf/modules/{bigquery,cloud_run_job,scheduler}/`, `tf/environments/production/`)
- [ ] tfstate の GCS バックエンド (バケット名・prefix) を決める
  - 参考実装 (preschool-agent, lofilab) はいずれも `backend "gcs"` のコメントで「事前に手動で作成しておく必要があります」と明記されており、バケット自体を作成する Terraform コードはリポジトリ内に見当たらない → 手動 bootstrap が前提と判断できる
  - 実際のバケットのラベル付け等の運用は GCP 側 (`gcloud storage buckets describe`) で確認が必要 (このリポジトリからは検証不可)
- [ ] raw 層ジョブ用サービスアカウントの権限範囲を決める
  - BigQuery: `roles/bigquery.dataEditor` + `roles/bigquery.jobUser` (参考実装の dbt SA 権限構成を踏襲)
  - Drive: IAM ロールでは付与できないため、Drive フォルダ側で SA のメールアドレスを共有設定する運用を確定する (手動作業として明記)
- [ ] コンテナイメージの配置先を決める。lofilab の共有 Artifact Registry (`utky-applications`) を使うか、raw 層専用リポジトリを作るか。ビルド/push 方法 (CI ワークフロー追加 or 手動 `docker build && push`) も決める
- [ ] `google_cloud_run_v2_job` に渡す環境変数 (`BQ_PROJECT_ID` / `BQ_DATASET_ID` / `BQ_TABLE_ID` / `DRIVE_CHILD_FOLDERS` / `LOG_LEVEL`) の terraform 変数化方針を決める (`DRIVE_CHILD_FOLDERS` は JSON 文字列なので tfvars での扱いを確認)
- [ ] BigQuery データセット/テーブルを Terraform 管理に含めるか、既存の手動作成物を import するかを決める
- [ ] 定期実行の頻度を決める。ぴよログのデータは月次ファイルをまとめて取り込むだけなので、preschool-agent (6時間おき) ほどの頻度は不要。日次1回の Cloud Scheduler → Cloud Run Jobs API 直接呼び出し (単一ジョブのため Workflow 経由は不要) を基本方針とする
- [ ] 上記構成をもとに Google Cloud の費用を見積もる (Cloud Run job 実行時間課金, BigQuery ストレージ/クエリ, Artifact Registry ストレージ, Cloud Scheduler 等)

### 実装

- [ ] `tf/environments/production/{main,variables,outputs}.tf` + `terraform.tfvars` を作成し、GCS バックエンドを設定する
- [ ] `tf/modules/bigquery/` を実装する (データセット + `export_files` テーブル定義)
- [ ] `tf/modules/cloud_run_job/` を実装する (サービスアカウント, IAM, `google_cloud_run_v2_job` リソース)
- [ ] `tf/modules/scheduler/` を実装する (日次 Cloud Scheduler → Cloud Run Jobs API 呼び出し用 SA と IAM)
- [ ] (lofilab 再利用と決めた場合) lofilab 側に raw 層用の設定 (GitHub Actions 対象リポジトリ追加など) を追加する。専用作成と決めた場合は Artifact Registry リポジトリ作成 + イメージビルド/push の手順を CI またはスクリプトに落とす
- [ ] Drive フォルダへの SA 共有設定を実施する (手動作業)
- [ ] `terraform plan` → `terraform apply` を実行し、Cloud Run job が実際に raw 層への取り込みを完走することを確認する

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
