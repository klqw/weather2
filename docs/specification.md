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

## weather_observations

気象観測データを管理する。

現時点でのテーブル構成案
- observation_id
- location_id
- observed_date
- avg_temp
- max_temp
- min_temp
- avg_humidity
- sunshine_hours
- avg_wind_speed
- max_snow_depth
- precipitation

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
psql -U postgres -d weather2 -f sql/create_locations.sql
psql -U postgres -d weather2 -f sql/create_weather_observations.sql

### ※ テーブルは残してデータだけ削除したい場合は
TRUNCATE TABLE locations RESTART IDENTITY;

## 実行時間メモ
$ time python ./download_jma.py --location 函館 --prefecture 渡島総合振興局
気象データのDB登録が完了しました。地点: 函館 - 渡島総合振興局, 登録件数: 55450件
地点マスタのDB更新が完了しました。地点: 函館 - 渡島総合振興局
real    11m40.332s
user    0m0.093s
sys     0m0.281s
