-- 寝る。detail_raw は向き・おくるみ等の短い自由メモのみで、構造化する値はない。
select
    {{ piyolog_event_columns() }},
    nullif(detail_raw, '') as memo,
    detail_raw
from {{ ref('int_piyolog__events') }}
where event_type = '寝る'
