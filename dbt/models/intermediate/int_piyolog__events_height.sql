-- 身長 (例: `66.0cm`)。
select
    {{ piyolog_event_columns() }},
    safe_cast(regexp_extract(detail_raw, r'^(\d+(?:\.\d+)?)cm') as numeric) as height_cm,
    {{ piyolog_detail_memo('detail_raw') }} as memo,
    detail_raw
from {{ ref('int_piyolog__events') }}
where event_type = '身長'
