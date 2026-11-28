-- 全種別のイベントを1テーブルに集約した intermediate の土台。
-- - 既知種別 (seed known_event_types) 以外は event_type を「その他」に寄せる (方針P)
-- - 種別ごとモデルから直接集計できるよう child_name / log_date を header から付与する
-- - 種別ごとモデルが毎回 UDF パースを再実行しないよう table で実体化する
{{ config(materialized='table') }}

with events as (

    select * from {{ ref('stg_piyolog__events') }}

),

headers as (

    select * from {{ ref('stg_piyolog__daily_headers') }}

),

known_event_types as (

    select * from {{ ref('known_event_types') }}

),

-- 未知種別を寄せる先 (その他) の event_group
fallback_group as (

    select event_group
    from known_event_types
    where event_type = 'その他'

),

joined as (

    select
        events.daily_header_id,
        events.event_seq,
        headers.child_name,
        headers.log_date,
        events.event_at,
        events.event_type_raw,
        events.detail_raw,
        known_event_types.event_type as known_event_type,
        coalesce(known_event_types.event_group, fallback_group.event_group) as event_group
    from events
    inner join headers on events.daily_header_id = headers.daily_header_id
    left join known_event_types on events.event_type_raw = known_event_types.event_type
    cross join fallback_group

)

select
    daily_header_id,
    event_seq,
    child_name,
    log_date,
    event_at,
    event_group,
    event_type_raw,
    detail_raw,
    concat(daily_header_id, ':', cast(event_seq as string)) as event_id,
    coalesce(known_event_type, 'その他') as event_type,
    known_event_type is null as is_unknown_event_type
from joined
