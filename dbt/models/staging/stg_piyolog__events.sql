with parsed as (

    select
        {{ function('parse_piyolog_export') }}(raw_content, child_name, source_year_month) as result
    from {{ source('piyolog_raw', 'export_files') }}

)

select
    event.daily_header_id,
    event.event_seq,
    event.event_at,
    event.event_type_raw,
    event.detail_raw
from parsed, unnest(parsed.result.events) as event
