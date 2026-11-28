-- 構造化しない種別 (event_group = free_text / routine / milestone) のイベント。
-- いずれも detail_raw が実質的に自由記述で、種別固有の列を持たないため、種別ごとに
-- テーブルを分けず event_type 列で絞り込む1モデルにまとめる (ADR-0011)。
-- 未知種別は int_piyolog__events で `その他` に寄せられてここに入る。元の種別は
-- event_type_raw で確認できる。
select
    {{ piyolog_event_columns() }},
    event_type,
    event_group,
    event_type_raw,
    is_unknown_event_type,
    nullif(detail_raw, '') as memo,
    detail_raw
from {{ ref('int_piyolog__events') }}
where event_group in ('free_text', 'routine', 'milestone')
