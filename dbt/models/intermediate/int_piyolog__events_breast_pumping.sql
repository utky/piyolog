-- 搾乳 (例: `10ml  左右 手搾り 冷凍`)。
select
    {{ piyolog_event_columns() }},
    safe_cast(regexp_extract(detail_raw, r'^(\d+)ml') as int64) as volume_ml,
    {{ piyolog_detail_memo('detail_raw') }} as memo,
    detail_raw
from {{ ref('int_piyolog__events') }}
where event_type = '搾乳'
