-- のみもの (例: `100ml  牛乳`)。補足メモに飲み物名が入る。
select
    {{ piyolog_event_columns() }},
    safe_cast(regexp_extract(detail_raw, r'^(\d+)ml') as int64) as volume_ml,
    {{ piyolog_detail_memo('detail_raw') }} as memo,
    detail_raw
from {{ ref('int_piyolog__events') }}
where event_type = 'のみもの'
