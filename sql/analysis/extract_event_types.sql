-- フェーズ2(種別棚卸し): raw_content から全期間・全子供のイベント種別を抽出し、
-- 出現頻度を集計する。BigQuery コンソール、または
--   bq query --project_id=<project> --use_legacy_sql=false < sql/analysis/extract_event_types.sql
-- で実行する。
--
-- イベント行は「HH:MM<スペース区切り>種別<スペース>詳細」の形式(実データで確認済み。
-- 区切りは半角スペースでタブではない。詳細は docs/piyolog_raw_layer_spec.md 参照)。
-- 種別名は空白を含まないため、時刻直後の最初の空白区切りトークンを種別として抽出する。

with lines as (
    select
        child_name,
        source_year_month,
        line
    from `lofilab.piyolog_raw.export_files`,
        UNNEST(SPLIT(raw_content, "\n")) as line
),

events as (
    select
        child_name,
        source_year_month,
        REGEXP_EXTRACT(line, r"^\d{1,2}:\d{2}\s+(\S+)") as event_type
    from lines
    where REGEXP_CONTAINS(line, r"^\d{1,2}:\d{2}\s")
)

select
    event_type,
    COUNT(*) as occurrence_count,
    COUNT(distinct child_name) as child_count,
    MIN(source_year_month) as first_seen_month,
    MAX(source_year_month) as last_seen_month
from events
group by event_type
order by occurrence_count desc
