# weather2 仕様メモ

## 目的

JMAの過去気象データを取得し、
PostgreSQLに蓄積して気象統計を作成する。

## 処理の流れ

JMA
↓
download_jma.py
↓
CSV（一時ファイル）
↓
register_jma.py
↓
PostgreSQL
↓
make_stats.py
↓
PostgreSQL

## locations

地点情報を管理する。

現時点でのテーブル構成案：

- location_id
- station_type
- block_no
- name
- kana
- latitude
- longitude
- elevation
- name_en
- prefecture_name
- prefecture_name_en
- start_date
- end_date (9999-12-31 = 現在も観測継続中)
- complete
- last_observation_update

## CSV -> DB登録 (download_jma.py -> register_jma.py)

- CSVの全項目がNaNの行は登録しない
- DB登録成功・失敗にかかわらずCSVを削除する
- DB登録が正常終了した場合のみcomplete=Trueにする
- 失敗した場合はcomplete=Falseのため次回同じ地点をまた取得
- download_jma.pyおよびregister_jma.py起動中は二重起動しないようにする

## 自動処理

Windowsではタスクスケジューラを使用する。

station_type="s", complete=Falseの地点を優先して処理する。

## next

main.py / card.py はいずれWebアプリに置き換える予定。

## テーブル初期化
psql -U postgres -d weather2 -f sql/create_tables.sql

### ※ テーブルは残してデータだけ削除したい場合は
TRUNCATE TABLE locations RESTART IDENTITY;
