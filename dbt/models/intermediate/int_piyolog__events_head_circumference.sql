-- 頭囲 (例: `43.0cm`)。
select
    {{ piyolog_event_columns() }},
    safe_cast(
        regexp_extract(detail_raw, r'^(\d+(?:\.\d+)?)cm') as numeric
    ) as head_circumference_cm,
    {{ piyolog_detail_memo('detail_raw') }} as memo,
    detail_raw
from {{ ref('int_piyolog__events') }}
where event_type = '頭囲'
