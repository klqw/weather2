import configparser
import logging
import json
import sys
from pathlib import Path
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
# データ集計
# --------------------

# 1件以上取得確認
def get_stats(cur, sql, stats_name, messages):
  cur.execute(sql)
  rows = cur.fetchall()

  if not rows:
    raise ValueError(
      messages["no_records_found"].format(table=stats_name)
    )

  return rows

# locationごと & 日ごとの平均値を全取得
def get_daily_avg_stats(config, stats_name, messages):
  sql = """
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
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name, messages)

  except psycopg.Error as e:
    raise RuntimeError(messages["get_stats_failed"]) from e

# locationごと & 月ごとの平均値を全取得
def get_month_avg_stats(config, stats_name, messages):
  sql = """
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
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name, messages)

  except psycopg.Error as e:
    raise RuntimeError(messages["get_stats_failed"]) from e

# locationごと & 全期間の平均値を取得
def get_overall_avg_stats(config, stats_name, messages):
  sql = """
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
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name, messages)

  except psycopg.Error as e:
    raise RuntimeError(messages["get_stats_failed"]) from e

# locationごと & 日ごとの最高値を全取得
def get_daily_max_stats(config, stats_name, messages):
  sql = """
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
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name, messages)

  except psycopg.Error as e:
    raise RuntimeError(messages["get_stats_failed"]) from e


# locationごと & 日ごとの最低値を全取得
def get_daily_min_stats(config, stats_name, messages):
  sql = """
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
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name, messages)

  except psycopg.Error as e:
    raise RuntimeError(messages["get_stats_failed"]) from e


# --------------------
# DB登録
# --------------------

# locationごと & 日ごとの平均値
def set_daily_avg_stats(cur, stats_data, stats_name, messages):
  sql = """
    INSERT INTO daily_avg_stats (
      location_id,
      month,
      day,
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
      %(month)s,
      %(day)s,
      %(avg_temp)s,
      %(max_temp)s,
      %(min_temp)s,
      %(avg_humidity)s,
      %(sunshine_hours)s,
      %(avg_wind_speed)s,
      %(precipitation)s,
      %(max_snow_depth)s
    )
    ON CONFLICT (location_id, month, day)
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
    cur.executemany(sql, stats_data)
    return len(stats_data)

  except psycopg.Error as e:
    raise RuntimeError(
      messages["set_stats_failed"].format(table=stats_name)
    ) from e

# locationごと & 月ごとの平均値
def set_month_avg_stats(cur, stats_data, stats_name, messages):
  sql = """
    INSERT INTO month_avg_stats (
      location_id,
      month,
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
      %(month)s,
      %(avg_temp)s,
      %(max_temp)s,
      %(min_temp)s,
      %(avg_humidity)s,
      %(sunshine_hours)s,
      %(avg_wind_speed)s,
      %(precipitation)s,
      %(max_snow_depth)s
    )
    ON CONFLICT (location_id, month)
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
    cur.executemany(sql, stats_data)
    return len(stats_data)

  except psycopg.Error as e:
    raise RuntimeError(
      messages["set_stats_failed"].format(table=stats_name)
    ) from e

# locationごと & 全期間の平均値
def set_overall_avg_stats(cur, stats_data, stats_name, messages):
  sql = """
    INSERT INTO overall_avg_stats (
      location_id,
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
      %(avg_temp)s,
      %(max_temp)s,
      %(min_temp)s,
      %(avg_humidity)s,
      %(sunshine_hours)s,
      %(avg_wind_speed)s,
      %(precipitation)s,
      %(max_snow_depth)s
    )
    ON CONFLICT (location_id)
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
    cur.executemany(sql, stats_data)
    return len(stats_data)

  except psycopg.Error as e:
    raise RuntimeError(
      messages["set_stats_failed"].format(table=stats_name)
    ) from e

# locationごと & 日ごとの最高値
def set_daily_max_stats(cur, stats_data, stats_name, messages):
  sql = """
    INSERT INTO daily_max_stats (
      location_id,
      month,
      day,
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
      %(month)s,
      %(day)s,
      %(avg_temp)s,
      %(max_temp)s,
      %(min_temp)s,
      %(avg_humidity)s,
      %(sunshine_hours)s,
      %(avg_wind_speed)s,
      %(precipitation)s,
      %(max_snow_depth)s
    )
    ON CONFLICT (location_id, month, day)
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
    cur.executemany(sql, stats_data)
    return len(stats_data)

  except psycopg.Error as e:
    raise RuntimeError(
      messages["set_stats_failed"].format(table=stats_name)
    ) from e

# locationごと & 日ごとの最低値
def set_daily_min_stats(cur, stats_data, stats_name, messages):
  sql = """
    INSERT INTO daily_min_stats (
      location_id,
      month,
      day,
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
      %(month)s,
      %(day)s,
      %(avg_temp)s,
      %(max_temp)s,
      %(min_temp)s,
      %(avg_humidity)s,
      %(sunshine_hours)s,
      %(avg_wind_speed)s,
      %(precipitation)s,
      %(max_snow_depth)s
    )
    ON CONFLICT (location_id, month, day)
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
    cur.executemany(sql, stats_data)
    return len(stats_data)

  except psycopg.Error as e:
    raise RuntimeError(
      messages["set_stats_failed"].format(table=stats_name)
    ) from e

# --------------------
# main処理
# --------------------
def main():
  # 設定ファイルの取得
  config = load_config()
  message_config = load_message_config(config)
  messages = message_config["make_stats"]

  logging.basicConfig(
    filename=config["LOG"]["log_file"],
    level=logging.INFO,
    encoding=config["LOG"]["log_encoding"],
    format="%(asctime)s %(levelname)s [%(filename)s] %(message)s"
  )

  # 5つの集計→登録処理を共通タスク化
  stats_tasks = [
    ("daily_avg_stats", get_daily_avg_stats, set_daily_avg_stats),
    ("month_avg_stats", get_month_avg_stats, set_month_avg_stats),
    ("overall_avg_stats", get_overall_avg_stats, set_overall_avg_stats),
    ("daily_max_stats", get_daily_max_stats, set_daily_max_stats),
    ("daily_min_stats", get_daily_min_stats, set_daily_min_stats)
  ]

  logging.info("========== START ==========")

  try:
    # --------------------
    # データ集計実行
    # --------------------
    stats_data = {}

    # location単位で、日ごと・月ごと・全期間の平均値・最高値・最低値を取得
    for name, getter, _ in stats_tasks:
      stats_data[name] = getter(config, name, messages)

    # --------------------
    # DB登録実行
    # --------------------
    with get_connection(config) as conn:
      with conn.cursor() as cur:
        for name, _, setter in stats_tasks:
          processed_count = setter(cur, stats_data[name], name, messages)

          message = messages["set_stats_done"].format(
            name=name,
            count=processed_count
          )
          print(message)
          logging.info(message)

  except (FileNotFoundError, ValueError, RuntimeError) as e:
    logging.error(str(e))
    print(f"エラー: {e}")
    sys.exit(1)

  finally:
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()