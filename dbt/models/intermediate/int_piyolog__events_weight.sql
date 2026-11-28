-- 体重。単位は `kg` (例: `8.50kg  服あり`) と `g` (例: `7935g`) が混在するため g に揃える。
with weight as (

    select
        *,
        regexp_extract(detail_raw, r'^(\d+(?:\.\d+)?)(?:kg|g)') as value_raw,
        regexp_extract(detail_raw, r'^\d+(?:\.\d+)?(kg|g)') as unit_raw
    from {{ ref('int_piyolog__events') }}
    where event_type = '体重'

)

select
    {{ piyolog_event_columns() }},
    cast(round(
        safe_cast(value_raw as numeric) * if(unit_raw = 'kg', 1000, 1)
    ) as int64) as weight_g,
    {{ piyolog_detail_memo('detail_raw') }} as memo,
    detail_raw
from weight
