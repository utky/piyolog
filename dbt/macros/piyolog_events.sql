{#
  intermediate の種別ごとモデルで共通に使うマクロ。
#}

{# 種別ごとモデルが先頭に持つ共通列。 #}
{% macro piyolog_event_columns() -%}
    event_id,
    daily_header_id,
    event_seq,
    child_name,
    log_date,
    event_at
{%- endmacro %}

{#
  値と補足メモを分ける。ぴよログは値 (例: `120ml`) の後に半角スペース2つを挟んで
  補足メモを書き出す (例: `120ml  お腹いっぱい`)。補足は改行を含みうるため (?s) を付ける。
  値型の種別にのみ使う (自由記述型は値と補足の区別がないため使わない)。
#}
{% macro piyolog_detail_memo(column) -%}
    nullif(regexp_extract({{ column }}, r'(?s)^.*?  (.*)$'), '')
{%- endmacro %}
