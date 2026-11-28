-- おしっこ。detail_raw はトイレトレーニングの記録 (例: `おまるで成功`) 等の自由メモ。
select
    {{ piyolog_event_columns() }},
    nullif(detail_raw, '') as memo,
    detail_raw
from {{ ref('int_piyolog__events') }}
where event_type = 'おしっこ'
