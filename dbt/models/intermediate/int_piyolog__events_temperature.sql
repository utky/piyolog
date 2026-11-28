-- 体温 (例: `36.8°C`)。
select
    {{ piyolog_event_columns() }},
    safe_cast(regexp_extract(detail_raw, r'^(\d+(?:\.\d+)?)°C') as numeric) as temperature_celsius,
    {{ piyolog_detail_memo('detail_raw') }} as memo,
    detail_raw
from {{ ref('int_piyolog__events') }}
where event_type = '体温'
