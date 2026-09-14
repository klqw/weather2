import logging
from pathlib import Path
import pandas as pd
import psycopg
from db import get_connection

# --------------------
# DB登録対象のCSV読み込み
# --------------------
def load_csv_files(data_dir, location_code, config):

  files = list(data_dir.glob(f"*_{location_code}_*.csv"))

  if not files:
    raise FileNotFoundError("CSVファイルがありません")

  dfs = []

  for file in files:
    logging.info("読み込み: %s", file)

    # 気象台, アメダスそれぞれの使用カラム指定
    usecols_map = {
      "s": [0, 1, 5, 8, 11, 14, 17, 21, 25],
      "a": [0, 1, 4, 7, 10, 13, 16, 19, 22]
    }
    usecols = usecols_map[location_code[0]]

    df = pd.read_csv(
      file,
      parse_dates=[config["COLUMN"]["date"]],
      encoding=config["CSV"]["input_encoding"],
      skiprows=[0, 1, 2, 4, 5],
      usecols=usecols
    )
    dfs.append(df)

  return pd.concat(dfs, ignore_index=True)

# --------------------
# 取得CSVからDB登録
# --------------------

def register_jma(location_data, config):
  input_dir = Path(config["PATH"]["data_dir"])

  # location_codeの設定
  location_code = location_data["station_type"] + location_data["block_no"]

  # SQL設定
  sql = """
    INSERT INTO weather_observations (
      location_id,
      observed_date,
      avg_temp,
      max_temp,
      min_temp,
      avg_humidity,
      sunshine_hours,
      avg_wind_speed,
      precipitation,
      max_snow_depth
    )
    VALUES (
      %(location_id)s,
      %(observed_date)s,
      %(avg_temp)s,
      %(max_temp)s,
      %(min_temp)s,
      %(avg_humidity)s,
      %(sunshine_hours)s,
      %(avg_wind_speed)s,
      %(precipitation)s,
      %(max_snow_depth)s
    )
    ON CONFLICT (location_id, observed_date)
    DO UPDATE SET
      avg_temp = EXCLUDED.avg_temp,
      max_temp = EXCLUDED.max_temp,
      min_temp = EXCLUDED.min_temp,
      avg_humidity = EXCLUDED.avg_humidity,
      sunshine_hours = EXCLUDED.sunshine_hours,
      avg_wind_speed = EXCLUDED.avg_wind_speed,
      precipitation = EXCLUDED.precipitation,
      max_snow_depth = EXCLUDED.max_snow_depth;
  """

  # location_id設定
  location_id = location_data["location_id"]

  # 戻り値初期設定
  first_registered_date = None
  last_registered_date = None
  registered_count = 0

  # df全空判定用
  weather_columns = [
    config["COLUMN"]["avg_tmp"],
    config["COLUMN"]["max_tmp"],
    config["COLUMN"]["min_tmp"],
    config["COLUMN"]["avg_humidity"],
    config["COLUMN"]["sunshine"],
    config["COLUMN"]["avg_wind"],
    config["COLUMN"]["precip"],
    config["COLUMN"]["max_snow"]
  ]

  try:
    # CSVからデータ取得
    df = load_csv_files(input_dir, location_code, config)

    # CSV取得データからDB登録(更新)
    with get_connection(config) as conn:
      with conn.cursor() as cur:
        for _, row in df.iterrows():

          observed_date = row[
            config["COLUMN"]["date"]
          ].date()

          if row[weather_columns].isna().all():
            continue

          observation_data = {
            "location_id": location_id,
            "observed_date": observed_date,
            "avg_temp": to_db_value(row[config["COLUMN"]["avg_tmp"]]),
            "max_temp": to_db_value(row[config["COLUMN"]["max_tmp"]]),
            "min_temp": to_db_value(row[config["COLUMN"]["min_tmp"]]),
            "avg_humidity": to_db_value(row[config["COLUMN"]["avg_humidity"]]),
            "sunshine_hours": to_db_value(row[config["COLUMN"]["sunshine"]]),
            "avg_wind_speed": to_db_value(row[config["COLUMN"]["avg_wind"]]),
            "precipitation": to_db_value(row[config["COLUMN"]["precip"]]),
            "max_snow_depth": to_db_value(row[config["COLUMN"]["max_snow"]])
          }

          cur.execute(sql, observation_data)
          registered_count += 1

          if (
            first_registered_date is None
            or
            observed_date < first_registered_date
          ):
            first_registered_date = observed_date

          if (
            last_registered_date is None
            or
            observed_date > last_registered_date
          ):
            last_registered_date = observed_date

    return first_registered_date, last_registered_date, registered_count

  except psycopg.Error as e:
    raise RuntimeError("気象データのDB登録に失敗しました") from e

# NaN->NULL登録
def to_db_value(value):
  return None if pd.isna(value) else value

# --------------------
# DB登録完了後地点マスタ更新
# --------------------
def update_locations(location_id, start_date, last_observation_update, config):
  sql = """
    UPDATE locations
    SET
      start_date = %s,
      complete = TRUE,
      last_observation_update = %s
    WHERE location_id = %s;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor() as cur:
        cur.execute(
          sql,
          (
            start_date,
            last_observation_update,
            location_id
          )
        )

  except psycopg.Error as e:
    raise RuntimeError("locationテーブルの更新に失敗しました") from e