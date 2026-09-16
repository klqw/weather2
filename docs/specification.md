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
- last_daily_update

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
psql -U postgres -d weather2 -f sql/create_stats.sql

### ※ テーブルは残してデータだけ削除したい場合は
TRUNCATE TABLE locations RESTART IDENTITY;

## 実行時間メモ
$ time python ./download_jma.py --location 函館 --prefecture 渡島総合振興局
気象データのDB登録が完了しました。地点: 函館 - 渡島総合振興局, 登録件数: 55451件
地点マスタのDB更新が完了しました。地点: 函館 - 渡島総合振興局
real    6m29.904s
user    0m0.234s
sys     0m0.218s

## 追加作成予定
日時更新用バッチ
daily_update.py

## make_stats DB取得

### daily_avg_stats
WITH daily_stats AS (
  SELECT
    location_id,
    EXTRACT(MONTH FROM observed_date) AS month,
    EXTRACT(DAY FROM observed_date) AS day,
    AVG(avg_temp) AS avg_temp,
    AVG(max_temp) AS max_temp,
    AVG(min_temp) AS min_temp,
    AVG(avg_humidity) AS avg_humidity,
    AVG(sunshine_hours) AS sunshine_hours,
    AVG(precipitation) AS precipitation,
    AVG(avg_wind_speed) AS avg_wind_speed,
    AVG(max_snow_depth) AS max_snow_depth
  FROM weather_observations
  GROUP BY
    location_id,
    EXTRACT(MONTH FROM observed_date),
    EXTRACT(DAY FROM observed_date)
)
SELECT
  d.location_id,
  l.name_en,
  l.prefecture_name_en,
  d.month,
  d.day,
  d.avg_temp,
  d.max_temp,
  d.min_temp,
  d.avg_humidity,
  d.sunshine_hours,
  d.precipitation,
  d.avg_wind_speed,
  d.max_snow_depth
FROM daily_stats AS d
JOIN locations AS l
  ON d.location_id = l.location_id
ORDER BY d.location_id;

### month_avg_stats
WITH month_stats AS (
  SELECT
    location_id,
    EXTRACT(MONTH FROM observed_date) AS month,
    AVG(avg_temp) AS avg_temp,
    AVG(max_temp) AS max_temp,
    AVG(min_temp) AS min_temp,
    AVG(avg_humidity) AS avg_humidity,
    AVG(sunshine_hours) AS sunshine_hours,
    AVG(precipitation) AS precipitation,
    AVG(avg_wind_speed) AS avg_wind_speed,
    AVG(max_snow_depth) AS max_snow_depth
  FROM weather_observations
  GROUP BY
    location_id,
    EXTRACT(MONTH FROM observed_date)
)
SELECT
  m.location_id,
  l.name_en,
  l.prefecture_name_en,
  m.month,
  m.avg_temp,
  m.max_temp,
  m.min_temp,
  m.avg_humidity,
  m.sunshine_hours,
  m.precipitation,
  m.avg_wind_speed,
  m.max_snow_depth
FROM month_stats AS m
JOIN locations AS l
  ON m.location_id = l.location_id
ORDER BY m.location_id;

### overall_avg_stats
WITH overall_stats AS (
  SELECT
    location_id,
    AVG(avg_temp) AS avg_temp,
    AVG(max_temp) AS max_temp,
    AVG(min_temp) AS min_temp,
    AVG(avg_humidity) AS avg_humidity,
    AVG(sunshine_hours) AS sunshine_hours,
    AVG(precipitation) AS precipitation,
    AVG(avg_wind_speed) AS avg_wind_speed,
    AVG(max_snow_depth) AS max_snow_depth
  FROM weather_observations
  GROUP BY location_id
)
SELECT
  o.location_id,
  l.name_en,
  l.prefecture_name_en,
  o.avg_temp,
  o.max_temp,
  o.min_temp,
  o.avg_humidity,
  o.sunshine_hours,
  o.precipitation,
  o.avg_wind_speed,
  o.max_snow_depth
FROM overall_stats AS o
JOIN locations AS l
  ON o.location_id = l.location_id
ORDER BY o.location_id;

### daily_max_stats
WITH daily_stats AS (
  SELECT
    location_id,
    EXTRACT(MONTH FROM observed_date) AS month,
    EXTRACT(DAY FROM observed_date) AS day,
    MAX(avg_temp) AS avg_temp,
    MAX(max_temp) AS max_temp,
    MAX(min_temp) AS min_temp,
    MAX(avg_humidity) AS avg_humidity,
    MAX(sunshine_hours) AS sunshine_hours,
    MAX(precipitation) AS precipitation,
    MAX(avg_wind_speed) AS avg_wind_speed,
    MAX(max_snow_depth) AS max_snow_depth
  FROM weather_observations
  GROUP BY
    location_id,
    EXTRACT(MONTH FROM observed_date),
    EXTRACT(DAY FROM observed_date)
)
SELECT
  d.location_id,
  l.name_en,
  l.prefecture_name_en,
  d.month,
  d.day,
  d.avg_temp,
  d.max_temp,
  d.min_temp,
  d.avg_humidity,
  d.sunshine_hours,
  d.precipitation,
  d.avg_wind_speed,
  d.max_snow_depth
FROM daily_stats AS d
JOIN locations AS l
  ON d.location_id = l.location_id
ORDER BY d.location_id;

### daily_min_stats
WITH daily_stats AS (
  SELECT
    location_id,
    EXTRACT(MONTH FROM observed_date) AS month,
    EXTRACT(DAY FROM observed_date) AS day,
    MIN(avg_temp) AS avg_temp,
    MIN(max_temp) AS max_temp,
    MIN(min_temp) AS min_temp,
    MIN(avg_humidity) AS avg_humidity,
    MIN(sunshine_hours) AS sunshine_hours,
    MIN(precipitation) AS precipitation,
    MIN(avg_wind_speed) AS avg_wind_speed,
    MIN(max_snow_depth) AS max_snow_depth
  FROM weather_observations
  GROUP BY
    location_id,
    EXTRACT(MONTH FROM observed_date),
    EXTRACT(DAY FROM observed_date)
)
SELECT
  d.location_id,
  l.name_en,
  l.prefecture_name_en,
  d.month,
  d.day,
  d.avg_temp,
  d.max_temp,
  d.min_temp,
  d.avg_humidity,
  d.sunshine_hours,
  d.precipitation,
  d.avg_wind_speed,
  d.max_snow_depth
FROM daily_stats AS d
JOIN locations AS l
  ON d.location_id = l.location_id
ORDER BY d.location_id;

## TODO
- CSVとDBの値照合
- make_stats.pyの関数部分微修正
- 自動巡回バッチ(最新データ取得用)