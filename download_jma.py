import argparse
import configparser
import csv
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

# --------------------
# 設定ファイル
# --------------------
def load_config():
  config = configparser.ConfigParser()

  base_dir = Path(__file__).resolve().parent
  config_file = base_dir / "config" / "config.ini"

  config.read(
    config_file,
    encoding="utf-8"
  )

  return config


# --------------------
# 地点マスタの取得
# --------------------

# 手動Ver
def get_manual_download_location(location, prefecture, config):
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
          raise ValueError(f"指定された地点が見つかりません 地点名: {location}, 都府県名: {prefecture}")

        return location_data

  except psycopg.Error as e:
    raise RuntimeError("locationテーブルからの取得に失敗しました") from e

# 自動Ver
def get_auto_download_location(config):
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
          raise ValueError("ダウンロード対象の地点が見つかりません")

        return location_data

  except psycopg.Error as e:
    raise RuntimeError("locationテーブルからの取得に失敗しました") from e


def load_locations(location, prefecture, config):
  location_dir = Path(config["PATH"]["location_dir"])
  locations_file = (location_dir / "locations.csv")

  try:
    with open(locations_file, encoding=config["CSV"]["output_encoding"], newline="") as f:
      reader = csv.DictReader(f)
      matches = [
        row for row in reader
        if row["name"] == location and row["prefecture_name"] == prefecture or
        row["name_en"] == location and row["prefecture_name_en"] == prefecture
      ]
      logging.info("手動ダウンロード対象 地点名: %s, 都府県名: %s", location, prefecture)

  except FileNotFoundError:
    raise FileNotFoundError("地点マスタCSVがありません")

  if len(matches) == 0:
    raise ValueError(f"指定された地点が見つかりません 地点名: {location}, 都府県名: {prefecture}")

  if len(matches) > 1:
    raise ValueError(f"指定された地点が複数見つかりました 地点名: {location}, 都府県名: {prefecture}")

  return matches[0]


# --------------------
# ダウンロード処理
# --------------------
def download_csv(loc_data, next_start_date, config):

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
    f'{loc_data["name_en"]}_{loc_data["station_type"]}{loc_data["block_no"]}_'
    f'{start_date.year}-{chunk_end_date.year}.csv'
  )

  # 出力パス設定
  output_dir = Path(config["PATH"]["data_dir"])
  output_dir.mkdir(parents=True, exist_ok=True)
  output_file = (output_dir / filename)

  # CSV取得URL設定
  url = config["URL"]["dl_url"]

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

  try:
    # DL処理
    response = requests.post(
      url, data=data,
      timeout=int(config["DOWNLOAD"]["request_timeout"])
    )

    response.raise_for_status()

    with open(output_file, "wb") as f:
      f.write(response.content)

    print(f"ダウンロード完了: {filename}")
    logging.info("ダウンロード完了: %s", filename)

    return next_start_date, end_date

  except requests.RequestException as e:
    raise RuntimeError(f"ファイルのダウンロードに失敗しました: {filename}") from e


# --------------------
# DB登録完了後のCSV削除
# --------------------
def delete_download_csv(location_data, config):
  # 一時保存CSV格納パス指定
  data_dir = Path(config["PATH"]["data_dir"])

  location_code = location_data["station_type"] + location_data["block_no"]

  files = list(data_dir.glob(f"*_{location_code}_*.csv"))

  for file in files:
    try:
      # 削除処理
      file.unlink()
      logging.info("CSV削除: %s", file)

    except OSError as e:
      logging.warning(
        "CSV削除に失敗しました: %s, エラー: %s",
        file, e
      )


# --------------------
# main処理
# --------------------
def main():
  config = load_config()
  location_data = None

  logging.basicConfig(
    filename=config["LOG"]["log_file"],
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
    description="地点指定ダウンロード"
  )

  parser.add_argument(
    "--location",
    help="地点名を漢字または英字で指定"
  )

  parser.add_argument(
    "--prefecture",
    help="都府県名を漢字または英字で指定"
  )

  args = parser.parse_args()

  if bool(args.location) != bool(args.prefecture):
    parser.error(
      "--location と --prefecture は両方指定するか、両方省略してください"
    )

  logging.info("========== START ==========")

  # --------------------
  # CSVのDL処理
  # --------------------
  try:
    if args.location and args.prefecture:
      # 指定した値で地点マスタから取得対象のデータを取得
      location_data = get_manual_download_location(args.location, args.prefecture, config)
    else:
      # 地点マスタから取得対象のデータを取得
      location_data = get_auto_download_location(config)

    # 古いデータから15年ごとにDLを行う
    while True:
      next_start_date, end_date = download_csv(location_data, next_start_date, config)

      if next_start_date > end_date:
        break

      time.sleep(download_interval)

    first_registered_date, last_registered_date, registered_count = register_jma(location_data, config)

    if registered_count == 0:
      raise ValueError(
        f"登録可能な気象データがありません。地点:{location_data['name']} - {location_data['prefecture_name']}"
      )
    
    print(
      f"気象データのDB登録が完了しました。地点: {location_data["name"]} - {location_data["prefecture_name"]}, 登録件数: {registered_count}件"
    )
    logging.info(
      "気象データのDB登録が完了しました。地点: %s - %s, 登録件数: %d件",
      location_data["name"], location_data["prefecture_name"], registered_count
    )

    update_locations(
      location_data["location_id"],
      first_registered_date,
      last_registered_date,
      config
    )
    
    print(
      f"地点マスタのDB更新が完了しました。地点: {location_data['name']} - {location_data['prefecture_name']}"
    )
    logging.info(
      "地点マスタのDB更新が完了しました。地点: %s - %s",
      location_data["name"], location_data["prefecture_name"]
    )

  except (FileNotFoundError, ValueError, RuntimeError) as e:
    print(f"エラー: {e}")
    logging.error(str(e))
    sys.exit(1)

  finally:
    if location_data is not None:
      delete_download_csv(location_data, config)
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()