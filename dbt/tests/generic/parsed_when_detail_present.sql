{#
  種別ごとモデルの構造化列が、detail_raw があるのに NULL になっている行を検知する。
  アプリ側の表記変更や想定外フォーマットによるパース漏れに気づくための品質ゲート (方針P)。
  既知の例外 (時間情報のない `母乳` 等) もあるため severity: warn で使う。
#}
{% test parsed_when_detail_present(model, column_name) %}

select *
from {{ model }}
where detail_raw != '' and {{ column_name }} is null

{% endtest %}
