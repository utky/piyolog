-- 母乳。左右の授乳時間と左右を結ぶ記号が先頭に入り、補足メモが続く。
-- 実データのフォーマット:
--   `左10分 ◀ 右10分` / `左10分 ▶ 右10分` / `左15分 / 右18分` / `左5分` / `右6分`
--   `左11分 ◀ 右10分 (120ml)` (量付き、まれ) / `母乳` (時間情報なし、まれ)
-- 記号 (▶ ◀ /) の意味 (どちらから飲ませたか) はアプリ仕様が未確認のため、
-- 解釈せず side_order_mark にそのまま残す。
with breastfeeding as (

    select
        *,
        regexp_extract(detail_raw, r'^左(\d+)分') as left_minutes_raw,
        regexp_extract(detail_raw, r'^(?:左\d+分 [▶◀/] )?右(\d+)分') as right_minutes_raw
    from {{ ref('int_piyolog__events') }}
    where event_type = '母乳'

)

select
    {{ piyolog_event_columns() }},
    safe_cast(left_minutes_raw as int64) as left_minutes,
    safe_cast(right_minutes_raw as int64) as right_minutes,
    if(
        left_minutes_raw is null and right_minutes_raw is null,
        null,
        coalesce(safe_cast(left_minutes_raw as int64), 0)
        + coalesce(safe_cast(right_minutes_raw as int64), 0)
    ) as total_minutes,
    regexp_extract(detail_raw, r'^左\d+分 ([▶◀/]) 右\d+分') as side_order_mark,
    safe_cast(regexp_extract(detail_raw, r'^[^\n]*?分 \((\d+)ml\)') as int64) as volume_ml,
    {{ piyolog_detail_memo('detail_raw') }} as memo,
    detail_raw
from breastfeeding
