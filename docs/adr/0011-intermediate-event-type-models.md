# ADR-0011: intermediate の種別ごとモデルは「構造化する種別だけ」個別に分け、既知種別は seed で一元管理する

## 状態
確定(2026-11-28、実データに対してモデルの SELECT を検証済み。本番 `dbt build` は未実施)

## 背景

[ADR-0001](0001-type-based-tables.md) で「イベント種別ごとに専用テーブルを持つ」と決めた。
根拠は「特定のイベントだけで集計する用途が主であり、種別固有スキーマのテーブルならビューを介さず
直接 SQL で集計できる」こと。フェーズ4で既知35種別の detail_raw を実データで調べたところ、
種別固有の列(数値・選択肢)を持てるのは一部で、残りは detail_raw が実質的に自由記述だった。

既知種別のリストは staging の `accepted_values` テスト(35値の直書き)と `docs/known_event_types.md`
の2か所にあり、intermediate で種別振り分けに使うと3か所目になる状況だった。

## 決定

1. **既知種別は seed `known_event_types`(`dbt/seeds/known_event_types.csv`)を単一の定義元にする。**
   列は `event_type` と `event_group`(intermediate での構造化方針)。
   - staging の未知種別検知は `accepted_values` の直書きをやめ、seed への `relationships` テスト
     (severity: warn)に置き換える。
   - seed は `piyolog_intermediate` データセットに置く(`dbt build` で他モデルより先に作られる)。
2. **土台モデル `int_piyolog__events`(table)を置く。** 全イベントに `child_name` / `log_date` を
   header から付与し、seed で `event_type` / `event_group` を確定させる。未知種別は
   `event_type = 'その他'` に寄せ、元の値は `event_type_raw`、寄せたかどうかは `is_unknown_event_type`
   で残す。主キー `event_id` = `{daily_header_id}:{event_seq}`。
   - staging は view で、参照のたびに Python UDF が raw 全件をパースし直す。種別ごとモデルとテストが
     それぞれ UDF を走らせないよう、土台だけ table で実体化する。
3. **detail_raw に構造がある種別(`event_group` = measurement / state / breastfeeding / training の
   15種別)は種別ごとに個別モデルを作る。** 種別固有の列(量・時間・選択肢)を持たせる。
4. **構造化しない種別(`event_group` = free_text / routine / milestone の20種別)は
   `int_piyolog__events_free_text` の1モデルにまとめ、`event_type` 列で絞り込む。**

## 根拠

- ADR-0001 の利点は「種別固有スキーマ」にある。自由記述の20種別はどれも
  `(共通列, detail_raw)` という同じ形で、種別ごとにテーブルを分けても固有の列は増えない。
  `where event_type = 'さんぽ'` を足すだけで集計できるため、20個の同形モデルを保守する価値がない。
- 構造化方針を seed の `event_group` に持たせたので、自由記述型 → 状態型への昇格(またはその逆)は
  seed の書き換えと個別モデルの追加・削除で済む。
- 未知種別を `その他` に寄せる処理が seed の join で表現でき、staging のテストと intermediate の
  振り分けが同じリストを見るので食い違わない。

## トレードオフ

- 自由記述の種別を個別テーブルとして参照したい用途(marts 等)では `event_type` で絞り込む必要がある。
  必要になったら marts 側か個別モデルとして切り出す。
- seed は `dbt build` のたびに再ロードされる(35行なのでコストは無視できる)。
- アプリ側の選択肢の記号(母乳の ▶ / ◀、マイオブレースの 🔴 / △ / ▲ / ❌)の意味は
  アプリ仕様を確認できていないため、記号のまま列に残し、意味づけはしない。
