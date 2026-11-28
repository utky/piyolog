-- マイオブレース (口腔筋機能トレーニング)。記録は大きく2系統:
--   - 夜間装着の結果: `朝までトライ🔴` / `朝までトライ△` / `朝までトライ▲` / `❌鼻水のため`
--   - 日中のトレーニング: `あいうべ体操` 等のメニューを改行区切りで並べ、最終行に
--     装着/実施時間 (例: `30分` / `20秒` / `1時間`) を書く
-- 結果記号の意味づけ (成功/一部成功 等) はアプリ仕様が未確認のため記号のまま残す。
with myobrace as (

    select
        *,
        regexp_extract(detail_raw, r'(?m)^(\d+)(?:秒|分|時間)\s*$') as duration_value_raw,
        regexp_extract(detail_raw, r'(?m)^\d+(秒|分|時間)\s*$') as duration_unit_raw
    from {{ ref('int_piyolog__events') }}
    where event_type = 'マイオブレース'

)

select
    {{ piyolog_event_columns() }},
    regexp_extract(detail_raw, r'(🔴|△|▲|❌)') as overnight_trial_result,
    safe_cast(duration_value_raw as int64) * case duration_unit_raw
        when '秒' then 1
        when '分' then 60
        when '時間' then 3600
    end as duration_seconds,
    nullif(detail_raw, '') as memo,
    detail_raw
from myobrace
