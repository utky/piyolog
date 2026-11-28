-- 起きる。直前の睡眠の継続時間 (例: `(1時間30分)`) を分に換算する。
-- 睡眠区間 (寝る → 起きる) の構築はフェーズ5で行い、ここでは継続時間の数値化のみ (方針Y)。
with wake_up as (

    select
        *,
        regexp_extract(detail_raw, r'^\((\d+)時間\d+分\)') as hours_raw,
        regexp_extract(detail_raw, r'^\(\d+時間(\d+)分\)') as minutes_raw
    from {{ ref('int_piyolog__events') }}
    where event_type = '起きる'

)

select
    {{ piyolog_event_columns() }},
    safe_cast(hours_raw as int64) * 60 + safe_cast(minutes_raw as int64) as sleep_duration_minutes,
    {{ piyolog_detail_memo('detail_raw') }} as memo,
    detail_raw
from wake_up
