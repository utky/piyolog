with parsed as (

    select
        {{ function('parse_piyolog_export') }}(raw_content, child_name, source_year_month) as result
    from {{ source('piyolog_raw', 'export_files') }}

)

select
    note.daily_header_id,
    note.note_raw
from parsed, unnest(parsed.result.notes) as note
