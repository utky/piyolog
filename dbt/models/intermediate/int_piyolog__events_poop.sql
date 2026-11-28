-- うんち。アプリの選択肢が `(量/硬さ/色)` の形で先頭に入り (例: `(多め/やわらかめ)`)、
-- その後に半角スペース2つを挟んで補足メモが続く。選択肢を選ばずメモだけの記録
-- (例: `大人トイレ`) もある。選択肢の語彙は量・硬さ・色ごとに既知の値へ振り分け、
-- 未知の語彙は poop_tags に残したうえでテストの警告で検知する (方針P)。
with poop as (

    select
        *,
        regexp_extract(detail_raw, r'^\(([^)]*)\)') as tags_raw
    from {{ ref('int_piyolog__events') }}
    where event_type = 'うんち'

),

tagged as (

    select
        *,
        if(tags_raw is null, [], split(tags_raw, '/')) as poop_tags
    from poop

)

select
    {{ piyolog_event_columns() }},
    poop_tags,
    (
        select tag from unnest(poop_tags) as tag with offset as tag_offset
        where tag in ('多め', '少なめ', 'ちょこっと')
        order by tag_offset
        limit 1
    ) as amount,
    (
        select tag from unnest(poop_tags) as tag with offset as tag_offset
        where tag in ('やわらかめ', 'かため', '下痢')
        order by tag_offset
        limit 1
    ) as consistency,
    (
        select tag from unnest(poop_tags) as tag with offset as tag_offset
        where tag in ('黄色', '橙', '緑', '茶色')
        order by tag_offset
        limit 1
    ) as color,
    if(
        tags_raw is null,
        nullif(detail_raw, ''),
        {{ piyolog_detail_memo('detail_raw') }}
    ) as memo,
    detail_raw
from tagged
