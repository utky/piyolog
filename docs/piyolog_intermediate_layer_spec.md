# ぴよログ → BigQuery: intermediate層(種別ごとモデル)仕様

## 0. このドキュメントの位置づけ

`piyolog_staging_layer_spec.md` の続き。staging層(`stg_piyolog__events` ほか)から
intermediate層の種別ごとモデル(`piyolog_intermediate.int_piyolog__events*`)への変換仕様。
設計判断の根拠は [ADR-0001](adr/0001-type-based-tables.md) / [ADR-0011](adr/0011-intermediate-event-type-models.md)。
区間データ(睡眠区間)・enrich はフェーズ5で扱う。

---

## 1. 構成

```
seed known_event_types (35種別, event_type → event_group)
          │
stg_piyolog__events ─┬─ stg_piyolog__daily_headers
                     ▼
int_piyolog__events (table)  全イベント + child_name / log_date / event_type / event_group
   ├─ measurement   : temperature / formula_milk / drink / breast_pumping /
   │                  expressed_breast_milk / weight / height / head_circumference /
   │                  chest_circumference
   ├─ state         : wake_up / sleep / pee / poop
   ├─ breastfeeding : breastfeeding
   ├─ training      : myobrace
   └─ free_text / routine / milestone : free_text (20種別を1モデルに集約)
```

種別ごとモデルは `int_piyolog__events_<entity>` で、すべて view(土台の table を参照するだけ)。

## 2. 共通列

全モデルが先頭に持つ列(マクロ `piyolog_event_columns()`):

| 列 | 型 | 内容 |
|---|---|---|
| `event_id` | STRING | `{daily_header_id}:{event_seq}`。主キー(unique / not_null テスト) |
| `daily_header_id` | STRING | `stg_piyolog__daily_headers` への外部キー |
| `event_seq` | INT64 | 日内の出現順 |
| `child_name` | STRING | header から付与(種別ごとモデルで直接集計できるよう非正規化) |
| `log_date` | DATE | header から付与 |
| `event_at` | DATETIME | イベント日時 |

種別ごとモデルは末尾に `memo`(補足メモ)と `detail_raw`(生テキスト。構造化で情報を落とさないため常に残す)を持つ。

### 値と補足メモの区切り

値型の種別では、アプリが値の後に**半角スペース2つ**を挟んで補足メモを書き出す
(例: `120ml  お腹いっぱい`)。マクロ `piyolog_detail_memo()` は最初の半角スペース2つ以降を
`memo` として取り出す(補足は改行を含みうる)。自由記述型は値と補足の区別がないため、
`detail_raw` が空でなければそのまま `memo` にする。

## 3. 土台: `int_piyolog__events`

| 列 | 内容 |
|---|---|
| 共通列 | §2 |
| `event_type` | 既知種別。seed に無い種別は `その他` |
| `event_group` | seed の `event_group`。未知種別は `その他` の group (`free_text`) |
| `event_type_raw` | staging の種別の生テキスト |
| `is_unknown_event_type` | `その他` に寄せた行なら true |
| `detail_raw` | staging の詳細の生テキスト |

table で実体化する(staging view を参照するたびに Python UDF が再実行されるのを避けるため)。

## 4. 種別ごとモデル

| モデル | 種別 | 構造化列 | 元の表記の例 |
|---|---|---|---|
| `_temperature` | 体温 | `temperature_celsius` NUMERIC | `36.8°C` |
| `_formula_milk` | ミルク | `volume_ml` INT64 | `120ml  お腹いっぱい` |
| `_drink` | のみもの | `volume_ml` INT64(飲み物名は `memo`) | `100ml  牛乳` |
| `_breast_pumping` | 搾乳 | `volume_ml` INT64 | `10ml  左右 手搾り 冷凍` |
| `_expressed_breast_milk` | 搾母乳 | `volume_ml` INT64 | `10ml` |
| `_weight` | 体重 | `weight_g` INT64(kg / g 混在を g に統一) | `8.50kg  服あり` / `7935g` |
| `_height` | 身長 | `height_cm` NUMERIC | `66.0cm` |
| `_head_circumference` | 頭囲 | `head_circumference_cm` NUMERIC | `43.0cm` |
| `_chest_circumference` | 胸囲 | `chest_circumference_cm` NUMERIC | `36.0cm` |
| `_wake_up` | 起きる | `sleep_duration_minutes` INT64(直前の睡眠の継続時間、方針Y) | `(1時間30分)` |
| `_sleep` | 寝る | なし(`memo` のみ) | `右向き` |
| `_pee` | おしっこ | なし(`memo` のみ) | `おまるで成功` |
| `_poop` | うんち | `poop_tags` ARRAY<STRING>, `amount`, `consistency`, `color` | `(多め/やわらかめ)  おまるで成功` |
| `_breastfeeding` | 母乳 | `left_minutes`, `right_minutes`, `total_minutes`, `side_order_mark`, `volume_ml` | `左10分 ◀ 右10分  寝落ち` |
| `_myobrace` | マイオブレース | `overnight_trial_result`, `duration_seconds` | `朝までトライ🔴` / `あいうべ体操\n30分` |
| `_free_text` | 自由記述・ルーティン・発達記録の20種別 + 未知種別 | `event_type`, `event_group`, `event_type_raw`, `is_unknown_event_type` | — |

### 種別ごとの補足

- **うんち**: 先頭の `(...)` を `/` で分割した選択肢を `poop_tags` に入れ、既知語彙で振り分ける。
  - `amount`: 多め / 少なめ / ちょこっと
  - `consistency`: やわらかめ / かため / 下痢
  - `color`: 黄色 / 橙 / 緑 / 茶色
  - 選択肢なしでメモだけの記録(`大人トイレ` 等)は `memo` に入る。
- **母乳**: フォーマットは `左N分 ◀ 右N分` / `左N分 ▶ 右N分` / `左N分 / 右N分` / `左N分` / `右N分`、
  まれに量付き `(Nml)` と時間情報なし(`母乳`)。`total_minutes` は片側のみなら片側の値、
  時間情報なしは NULL。記号 ▶ / ◀ / / の意味(どちらから飲ませたか)はアプリ仕様を
  確認できていないため `side_order_mark` に記号のまま残す。
- **マイオブレース**: 夜間装着の結果(`朝までトライ🔴` 等、`❌鼻水のため`)の記号を
  `overnight_trial_result` に、単独行で書かれた時間(`30分` / `20秒` / `1時間`)を秒に換算して
  `duration_seconds` に入れる。トレーニングメニュー(`あいうべ体操` 等)は `memo` に残す。
  記号の意味づけはしない。
- **白湯**: `docs/known_event_types.md` のフェーズ2時点の分類は数値/量型だったが、127件中123件が
  空欄で量の記録は1件のみのため free_text として扱う。

## 5. テスト(品質ゲート)

| テスト | 対象 | severity |
|---|---|---|
| `unique` / `not_null` | 全モデルの `event_id` | error |
| `relationships` → seed | `int_piyolog__events.event_type` | error |
| `relationships` → seed | `stg_piyolog__events.event_type_raw`(未知種別検知、方針P) | warn |
| `accepted_values` | `int_piyolog__events.event_group` | error |
| `parsed_when_detail_present`(generic) | 数値列(`temperature_celsius` / `volume_ml` / `weight_g` / `*_cm` / `sleep_duration_minutes` / `total_minutes`) | warn |
| `accepted_values` | `side_order_mark` / `overnight_trial_result` | warn |
| `assert_int_piyolog__events_poop_known_tags`(singular) | うんちの未知の選択肢 | warn |

`parsed_when_detail_present` は「detail_raw が空でないのに構造化列が NULL」の行を検知する。
アプリの表記変更によるパース漏れに気づくためのもの。2026-11 時点の実データでは、
母乳の `母乳`(5件)と起きるの `( ! )`(4件)が既知の例外として警告になる。

## 6. 検証結果(2026-11-28)

本番データセットに書き込まず、BigQuery のスクリプト内一時テーブルで各モデルの SELECT を実データに適用した。

- `int_piyolog__events` は 66,756 件で、種別ごとモデルの件数の合計と一致(漏れ・重複なし)。`event_id` は全モデルで一意。
- 未知種別は0件。
- 数値列のパース漏れは上記の既知例外のみ(体温・ミルク・のみもの・搾乳・搾母乳・体重・身長・頭囲・胸囲は0件)。
