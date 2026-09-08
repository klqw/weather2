import argparse
import configparser
import csv
import time
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import requests
import json

# --------------------
# 設定ファイル
# --------------------
def load_config():
  config = configparser.ConfigParser()

  config.read(
    "config.ini",
    encoding="utf-8"
  )

  return config


# --------------------
# 地点マスタの取得
# --------------------
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

  except FileNotFoundError:
    raise FileNotFoundError("地点マスタCSVがありません")

  if len(matches) == 0:
    raise ValueError(f"指定された地点が見つかりません 地点名: {location}, 都府県名: {prefecture}")

  if len(matches) > 1:
    raise ValueError(f"指定された地点が複数見つかりました 地点名: {location}, 都府県名: {prefecture}")

  return matches[0]


# --------------------
# 指定した地点のデータCSV取得
# --------------------
def manual_download_csv(loc_data, next_start_date, config):

  # チャンク(データ取得年数間隔)
  chunk_years = int(config["DOWNLOAD"]["chunk_years"])

  # マスタから取得した開始日時
  start_date = datetime.strptime(loc_data["start_date"], "%Y-%m-%d").date()

  # 引数で受け取った開始日時とマスタから取得した開始日時の新しい方を再設定
  start_date = max(start_date, next_start_date)

  # 取得可能最終日(昨日)
  yesterday = date.today() - timedelta(days=1)

  # 次の開始日時
  next_start_date = start_date.replace(
    year=start_date.year + chunk_years
  )

  # 終了日時(次の開始日時の前日)
  chunk_end_date = next_start_date - timedelta(days=1)

  # 終了日時と取得可能最終日の古い方を再設定
  chunk_end_date = min(chunk_end_date, yesterday)

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
    f'{loc_data["name_en"]}_'
    f'{start_date.year}-{chunk_end_date.year}.csv'
  )

  # 出力パス設定
  output_dir = Path(config["PATH"]["data_dir"])
  output_dir.mkdir(parents=True, exist_ok=True)
  output_file = (output_dir / filename)

  # CSV取得URL設定
  url = config["URL"]["dl_url"]

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
    "interAnnualType": "2",
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

  response = requests.post(
    url, data=data,
    timeout=int(config["DOWNLOAD"]["request_timeout"])
  )

  response.raise_for_status()

  with open(output_file, "wb") as f:
    f.write(response.content)
    print(f"DL完了: {filename}")

  return next_start_date


# --------------------
# main処理
# --------------------
def main():

  config = load_config()
  # 取得開始日時初期設定
  next_start_date = date(1, 1, 1)
  # 取得可能日時設定
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
    required=True,
    help="地点名を漢字で指定"
  )

  parser.add_argument(
    "--prefecture",
    required=True,
    help="都府県名を漢字で指定"
  )

  args = parser.parse_args()


  # --------------------
  # CSVのDL処理
  # --------------------
  try:
    # 地点マスタから取得対象のデータを格納
    location_data = load_locations(args.location, args.prefecture, config)

    # 古いデータから15年ごとにDLを行う
    while True:
      next_start_date = manual_download_csv(location_data, next_start_date, config)

      if next_start_date > end_date:
        break

      time.sleep(download_interval)

  except (FileNotFoundError, ValueError) as e:
    print(f"エラー: {e}")
    sys.exit(1)


if __name__ == "__main__":
  main()