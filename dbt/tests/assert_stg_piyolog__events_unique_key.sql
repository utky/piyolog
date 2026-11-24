-- events の一意制約は (daily_header_id, event_seq) の複合キー。
-- dbt_utils を追加せず、単発テストで直接検証する。
select
    daily_header_id,
    event_seq,
    count(*) as row_count
from {{ ref('stg_piyolog__events') }}
group by daily_header_id, event_seq
having count(*) > 1
