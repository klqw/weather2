import argparse
import configparser
import time
import logging
import sys
from pathlib import Path
from datetime import date, timedelta
import requests
import json
import psycopg
from psycopg.rows import dict_row
from db import get_connection
from register_jma import register_jma
from register_jma import update_locations

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
# 地点マスタの取得
# --------------------

# 手動Ver
def get_manual_download_location(location, prefecture, config, messages):
  sql = f"""
    SELECT
      location_id,
      station_type,
      block_no,
      name,
      name_en,
      prefecture_name,
      prefecture_name_en,
      start_date,
      end_date,
      complete,
      last_observation_update
    FROM locations
    WHERE
      (name = %s AND prefecture_name = %s)
      OR
      (name_en = %s AND prefecture_name_en = %s)
    LIMIT 1;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
          sql,
          (location, prefecture, location, prefecture)
        )
        location_data = cur.fetchone()

        if location_data is None:
          raise ValueError(
            messages["no_location"].format(location=location, prefecture=prefecture)
          )

        return location_data

  except psycopg.Error as e:
    raise RuntimeError(messages["get_locations_failed"]) from e

# 自動Ver
def get_auto_download_location(config, messages):
  sql = """
    SELECT
      location_id,
      station_type,
      block_no,
      name,
      name_en,
      prefecture_name,
      prefecture_name_en,
      start_date,
      end_date,
      complete,
      last_observation_update
    FROM locations
    WHERE
      complete = FALSE
      OR
      end_date >= CURRENT_DATE
    ORDER BY
      CASE
        WHEN station_type = 's' AND complete = FALSE THEN 1
        WHEN station_type = 'a' AND complete = FALSE THEN 2
        ELSE 3
      END,
      last_observation_update ASC NULLS FIRST
    LIMIT 1;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        location_data = cur.fetchone()

        if location_data is None:
          raise ValueError(messages["location_not_found"])

        return location_data

  except psycopg.Error as e:
    raise RuntimeError(messages["get_locations_failed"]) from e


# --------------------
# ダウンロード処理
# --------------------
def download_csv(loc_data, next_start_date, config, messages):

  # チャンク(データ取得年数間隔)
  chunk_years = int(config["DOWNLOAD"]["chunk_years"])

  # マスタから取得した開始日時
  start_date = loc_data["start_date"]

  # 引数で受け取った開始日時とマスタから取得した開始日時の新しい方を再設定
  start_date = max(start_date, next_start_date)

  # 取得可能最終日(9999-12-31の場合は前日の日付、それ以外はend_date)
  if str(loc_data["end_date"].year) == "9999":
    end_date = date.today() - timedelta(days=1)
  else:
    end_date = loc_data["end_date"]

  # CSV取得URL設定
  url = config["URL"]["dl_url"]

  # ダウンロードのために必要な値を設定
  next_start_date, filename, output_file, data = make_chunk(
    start_date, end_date, chunk_years, loc_data, config
  )

  # whileで504のときにretry
  retry_count = int(config["DOWNLOAD"]["retry_count"])
  retry_interval = int(config["DOWNLOAD"]["retry_interval"])
  attempt = 0
  while True:
    try:
      # DL処理
      response = requests.post(
        url, data=data,
        timeout=int(config["DOWNLOAD"]["request_timeout"])
      )

      response.raise_for_status()

      with open(output_file, "wb") as f:
        f.write(response.content)

      message = messages["download_done"].format(filename=filename)
      print(message)
      logging.info(message)

      return next_start_date, end_date

    except requests.HTTPError as e:
      # HTTPレスポンスステータスコード取得
      status_code = (
        e.response.status_code
        if e.response is not None
        else None
      )

      # ステータスコード504だけリトライ
      if status_code == 504:
        # 2回までリトライ
        if attempt < retry_count:
          attempt += 1
          retry_message = messages["gateway_timeout"].format(
            filename=filename,
            retry_interval=retry_interval,
            attempt=attempt,
            retry_count=retry_count
          )
          print(retry_message)
          logging.warning(retry_message)
          time.sleep(retry_interval)
          continue

        # リトライ全滅 -> チャンクの値を縮小して再度実行
        if chunk_years > 1:
          chunk_years = max(1, chunk_years // 2)
          attempt = 0

          next_start_date, filename, output_file, data = make_chunk(
            start_date, end_date, chunk_years, loc_data, config
          )

          retry_message = messages["chunk_reduction"].format(
            chunk_years=chunk_years,
            filename=filename
          )
          print(retry_message)
          logging.warning(retry_message)

          continue

      raise RuntimeError(messages["download_failed"].format(filename=filename)) from e

    except requests.RequestException as e:
      raise RuntimeError(messages["download_failed"].format(filename=filename)) from e


# ダウンロード時に渡す値を設定
def make_chunk(start_date, end_date, chunk_years, loc_data, config):

  # 次の開始日時
  next_start_date = start_date.replace(
    year=start_date.year + chunk_years
  )

  # 終了日時(次の開始日時の前日)
  chunk_end_date = next_start_date - timedelta(days=1)

  # 終了日時と取得可能最終日の古い方を再設定
  chunk_end_date = min(chunk_end_date, end_date)

  # DL処理時に渡す値を設定
  station_num_list = loc_data["station_type"] + loc_data["block_no"]
  ymd_list = [
    str(start_date.year),
    str(chunk_end_date.year),
    str(start_date.month),
    str(chunk_end_date.month),
    str(start_date.day),
    str(chunk_end_date.day)
  ]

  # 出力ファイル名設定
  filename = (
    f'{loc_data["name_en"]}_{station_num_list}_'
    f'{start_date.year}-{chunk_end_date.year}.csv'
  )

  # 出力パス設定
  output_dir = Path(config["PATH"]["data_dir"])
  output_dir.mkdir(parents=True, exist_ok=True)
  output_file = (output_dir / filename)

  # DL情報設定
  data = {
    "stationNumList": json.dumps([station_num_list]),
    "aggrgPeriod": "1",
    "elementNumList": json.dumps([
      ["101",""],   # 合計降水量
      ["201",""],   # 平均気温
      ["202",""],   # 最高気温
      ["203",""],   # 最低気温
      ["301",""],   # 平均湿度
      ["401",""],   # 平均風速
      ["501",""],   # 日照時間
      ["605",""]    # 合計積雪量
    ]),
    "interAnnualType": "1",
    "ymdList": json.dumps(ymd_list),
    "optionNumList": "[]",
    "downloadFlag": "true",
    "rmkFlag": "1",
    "disconnectFlag": "1",
    "youbiFlag": "0",
    "fukenFlag": "0",
    "kijiFlag": "0",
    "csvFlag": "1",
    "jikantaiFlag": "0",
    "jikantaiList": "[]",
    "ymdLiteral": "1",
  }

  return next_start_date, filename, output_file, data


# --------------------
# DB登録完了後のCSV削除
# --------------------
def delete_download_csv(location_data, config, messages):
  # 一時保存CSV格納パス指定
  data_dir = Path(config["PATH"]["data_dir"])

  location_code = location_data["station_type"] + location_data["block_no"]

  files = list(data_dir.glob(f"*_{location_code}_*.csv"))

  for file in files:
    try:
      # 削除処理
      file.unlink()
      logging.info(messages["file_delete_done"].format(path=file))

    except OSError as e:
      logging.warning(
        messages["file_delete_failed"].format(path=file, error=e)
      )


# --------------------
# main処理
# --------------------
def main():
  # 設定ファイルの取得
  config = load_config()
  message_config = load_message_config(config)
  messages_download = message_config["download_jma"]
  messages_register = message_config["register_jma"]
  location_data = None

  # ログ設定
  log_file = Path(config["LOG"]["log_file"])
  log_file.parent.mkdir(parents=True, exist_ok=True)
  logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    encoding=config["LOG"]["log_encoding"],
    format="%(asctime)s %(levelname)s [%(filename)s] %(message)s"
  )

  # 取得開始日時初期設定
  next_start_date = date(1, 1, 1)
  # 取得可能最終日時設定
  end_date = date.today() - timedelta(days=1)
  # DL待機時間設定
  download_interval = int(config["DOWNLOAD"]["download_interval"])

  # --------------------
  # CLI
  # --------------------
  parser = argparse.ArgumentParser(
    description=messages_download["parser_description"]
  )

  parser.add_argument(
    "--location",
    help=messages_download["parser_location"]
  )

  parser.add_argument(
    "--prefecture",
    help=messages_download["parser_prefecture"]
  )

  args = parser.parse_args()

  if bool(args.location) != bool(args.prefecture):
    parser.error(
      messages_download["parser_error"]
    )

  logging.info("========== START ==========")

  # --------------------
  # CSVのDL処理
  # --------------------
  try:
    if args.location and args.prefecture:
      # 指定した値で地点マスタから取得対象のデータを取得
      location_data = get_manual_download_location(args.location, args.prefecture, config, messages_download)
    else:
      # 地点マスタから取得対象のデータを取得
      location_data = get_auto_download_location(config, messages_download)

    # 古いデータから15年ごとにDLを行う
    while True:
      next_start_date, end_date = download_csv(location_data, next_start_date, config, messages_download)

      if next_start_date > end_date:
        break

      time.sleep(download_interval)

    first_registered_date, last_registered_date, registered_count = register_jma(location_data, config, messages_register)

    if registered_count == 0:
      raise ValueError(
        messages_download["no_records_found"].format(
          location=location_data['name'],
          prefecture=location_data['prefecture_name']
        )
      )
    
    message = messages_download["register_jma_done"].format(
      location=location_data["name"],
      prefecture=location_data["prefecture_name"],
      count=registered_count
    )
    print(message)
    logging.info(message)

    update_locations(
      location_data["location_id"],
      first_registered_date,
      last_registered_date,
      config,
      messages_register
    )

    update_message = messages_download["update_locations_done"].format(
      location=location_data["name"],
      prefecture=location_data["prefecture_name"]
    )
    print(update_message)
    logging.info(update_message)

  except (FileNotFoundError, ValueError, RuntimeError) as e:
    print(f"エラー: {e}")
    logging.error(str(e))
    sys.exit(1)

  finally:
    if location_data is not None:
      delete_download_csv(location_data, config, messages_download)
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()