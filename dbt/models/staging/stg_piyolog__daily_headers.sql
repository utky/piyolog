with parsed as (

    select
        {{ function('parse_piyolog_export') }}(raw_content, child_name, source_year_month) as result
    from {{ source('piyolog_raw', 'export_files') }}

)

select
    header.daily_header_id,
    header.child_name,
    header.source_year_month,
    header.log_date,
    header.child_age_raw
from parsed, unnest(parsed.result.headers) as header
