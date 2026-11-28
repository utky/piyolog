-- うんちの選択肢 `(量/硬さ/色)` に、amount / consistency / color のどれにも
-- 振り分けられない未知の語彙が出たら警告する (方針P)。
{{ config(severity='warn') }}

select
    poop.event_id,
    tag
from {{ ref('int_piyolog__events_poop') }} as poop, unnest(poop.poop_tags) as tag
where tag not in (
    '多め', '少なめ', 'ちょこっと',
    'やわらかめ', 'かため', '下痢',
    '黄色', '橙', '緑', '茶色'
)
