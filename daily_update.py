import configparser
import requests
import logging
import json
import time
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date, timedelta
import psycopg
from psycopg.rows import dict_row
from db import get_connection

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config" / "config.ini"

# --------------------
# 設定ファイル
# --------------------
def load_config():
  config = configparser.ConfigParser()
  config.read(CONFIG_FILE, encoding="utf-8")
  return config

def load_message_config(config):
  filename = (
    BASE_DIR / config["PATH"]["config_dir"] / config["FILE"]["messages"]
  )

  with open(filename, encoding="utf-8") as f:
    return json.load(f)


# --------------------
# 地点情報を取得
# --------------------
def get_locations(config, messages):
  sql = """
    SELECT
      location_id,
      station_type,
      block_no,
      prec_no,
      name,
      prefecture_name,
      COALESCE(
        last_daily_update,
        last_observation_update
      ) AS last_update
    FROM locations
    WHERE
      complete = TRUE
      AND end_date = '9999-12-31'
      AND (
        last_daily_update IS NULL
        OR last_daily_update < CURRENT_DATE
      )
    ORDER BY last_update ASC NULLS FIRST;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        locations_data = cur.fetchall()

        return locations_data

  except psycopg.Error as e:
    raise RuntimeError(messages["get_locations_failed"]) from e


# --------------------
# 更新先アクセス
# --------------------

# URL取得
def get_url(location, start_date):
  url = (
    f"https://www.data.jma.go.jp/stats/etrn/view/daily_{location["station_type"]}1.php"
    f"?prec_no={location["prec_no"]}"
    f"&block_no={location["block_no"]}"
    f"&year={start_date.year}"
    f"&month={start_date.month}"
    "&day="
    "&view="
  )
  return url

# 日別観測値取得
def get_weather_data(url, location, start_date, config, messages):
  # 間隔
  # 地点, 都府県
  name, prefecture_name = (location["name"], location["prefecture_name"])

  # request -> response
  try:
    response = requests.get(url, timeout=int(config["DOWNLOAD"]["request_timeout"]))
    response.raise_for_status()

  except requests.RequestException as e:
    raise RuntimeError(
      messages["request_failed"].format(
        location=name,
        prefecture=prefecture_name,
        url=url
      )
    ) from e

  # responseから日別観測値取得
  try:
    soup = BeautifulSoup(response.text, "html.parser")

    table = soup.find("table", id="tablefix1")

    if table is None:
      raise ValueError(
        messages["table_not_found"].format(
          location=name,
          prefecture=prefecture_name,
          url=url
        )
      )
    
    year = start_date.year
    month = start_date.month
    weather_data_list = []

    # station_typeごとのカラム位置設定
    COLUMN_MAPS = {
      "a": {
        "precipitation": 1,
        "avg_temp": 4,
        "max_temp": 5,
        "min_temp": 6,
        "avg_humidity": 7,
        "avg_wind_speed": 9,
        "sunshine_hours": 15,
        "max_snow_depth": 17,
      },
      "s": {
        "precipitation": 3,
        "avg_temp": 6,
        "max_temp": 7,
        "min_temp": 8,
        "avg_humidity": 9,
        "avg_wind_speed": 11,
        "sunshine_hours": 16,
        "max_snow_depth": 18,
      }
    }

    # station_typeの取得
    station_type = location["station_type"]

    if station_type not in COLUMN_MAPS:
      raise ValueError(
        messages["invalid_station_type"].format(station_type=station_type)
      )

    # 取得したstation_typeに対応するカラム位置の取得
    column_map = COLUMN_MAPS[location["station_type"]]

    for row in table.find_all("tr", class_="mtx"):
      cells = row.find_all("td")

      # ヘッダ行はtdがないので除外
      if not cells:
        continue

      day = int(cells[0].get_text(strip=True))

      # 観測値以外の値を設定
      weather_data = {
        "location_id": location["location_id"],
        "observed_date": date(year, month, day)
      }

      for column, index in column_map.items():
        # Weather_observations登録用に型変換しながら格納
        weather_data[column] = to_float(cells[index].get_text(strip=True))

      # 観測値すべてNoneの場合はスキップ
      if all(weather_data[column] is None for column in column_map):
        continue

      weather_data_list.append(weather_data)

    return weather_data_list

  except ValueError:
    raise

  except (IndexError, KeyError, TypeError, AttributeError) as e:
    raise RuntimeError(
        messages["parse_failed"].format(
        location=name,
        prefecture=prefecture_name,
        year=year,
        month=month
      )
    ) from e

# 計測値をfloat or Noneに変換
def to_float(value):
  value = value.replace(")", "").replace("]", "").strip()

  if value in ("--", "", "///"):
    return None

  return float(value)


# --------------------
# weather_observations更新
# --------------------
def set_weather_data(cur, location, weather_data, messages):
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

  try:
    cur.executemany(sql, weather_data)
    return len(weather_data)

  except psycopg.Error as e:
    raise RuntimeError(
      messages["set_weather_data_failed"].format(        
        location=location["name"],
        prefecture=location["prefecture_name"]
      )
    ) from e


# --------------------
# locations更新
# --------------------
def update_locations(cur, location, last_daily_update, messages):
  # SQL設定
  sql = """
    UPDATE locations
    SET
      last_daily_update = %s
    WHERE location_id = %s;
  """

  try:
    cur.execute(
      sql,
      (last_daily_update, location["location_id"])
    )

  except psycopg.Error as e:
    raise RuntimeError(
      messages["update_locations_failed"].format(
        location=location["name"],
        prefecture=location["prefecture_name"]
      )
    ) from e


# --------------------
# main処理
# --------------------
def main():
  # 設定ファイルの取得
  config = load_config()
  message_config = load_message_config(config)
  messages = message_config["daily_update"]

  # バッチ実行日と観測終了日の日付を設定
  batch_date = date.today()
  end_date = batch_date - timedelta(days=1)

  # 件数カウント用
  success_count = 0
  error_count = 0
  total_processed_count = 0

  # request待機時間設定
  request_interval = float(config["DOWNLOAD"]["request_interval"])

  logging.basicConfig(
    filename=config["LOG"]["log_file"],
    level=logging.INFO,
    encoding=config["LOG"]["log_encoding"],
    format="%(asctime)s %(levelname)s [%(filename)s] %(message)s"
  )

  logging.info("========== START ==========")

  try:
    # 更新対象の地点取得
    location_data = get_locations(config, messages)

    # 地点ごとに日別観測値取得 -> weather_observationsテーブル登録
    for location in location_data:
      try:
        # 地点, 都府県
        name, prefecture_name = (location["name"], location["prefecture_name"])

        # set_weather_dataに渡す用list
        weather_data_list = []

        # 観測開始日を設定
        start_date = location["last_update"] - timedelta(days=2)
        current_date = start_date

        # 日別観測値を取得
        while current_date <= end_date:
          url = get_url(location, current_date)

          try:
            data = get_weather_data(url, location, current_date, config, messages)
          finally:
            time.sleep(request_interval)
            
          weather_data_list.extend(data)

          # 翌月へ
          if current_date.month == 12:
            current_date = date(
              current_date.year + 1,
              1,
              1
            )
          else:
            current_date = date(
              current_date.year,
              current_date.month + 1,
              1
            )

        # DB更新
        with get_connection(config) as conn:
          with conn.cursor() as cur:
            # weather_observationsを更新
            processed_count = set_weather_data(cur, location, weather_data_list, messages)

            # locationsを更新
            update_locations(cur, location, batch_date, messages)

        # 成功件数加算
        success_count += 1
        total_processed_count += processed_count

        message = messages["update_done"].format(
          location=name,
          prefecture=prefecture_name,
          start_date=start_date,
          end_date=end_date,
          count=processed_count
        )

        print(message)
        logging.info(message)

      except (ValueError, RuntimeError) as e:
        error_count += 1
        logging.error(str(e))
        print(f"エラー: {e}")
        continue

    # 全地点更新後に表示
    summary_message = messages["batch_done"].format(
      success_count=success_count,
      error_count=error_count,
      count=total_processed_count
    )
    print(summary_message)
    logging.info(summary_message)

    if error_count > 0:
      sys.exit(1)
  
  except (ValueError, RuntimeError) as e:
    logging.error(str(e))
    print(f"エラー: {e}")
    sys.exit(1)

  finally:
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()