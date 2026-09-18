import configparser
import re
import requests
import csv
import json
import logging
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date
import psycopg
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
# 地点マスタ生成のための情報取得
# --------------------
def get_prec_no(input_file, messages):
  try:
    with open(input_file, encoding="utf-8", newline="") as f:
      reader = csv.DictReader(f)
      return list(reader)

  except FileNotFoundError:
    raise FileNotFoundError(messages["prec_no_not_found"].format(path=input_file))

def get_stations(prec_no, config):
  params = {
    "prec_no": prec_no["prec_no"],
    "block_no": "",
    "year": "",
    "month": "",
    "day": "",
    "view": "",
  }

  response = requests.get(
    config["URL"]["jma_url"], params=params,
    timeout=int(config["DOWNLOAD"]["request_timeout"])
  )
  response.raise_for_status()

  soup = BeautifulSoup(response.text, "html.parser")

  stations = {}

  for area in soup.select("map area[onmouseover]"):
    onmouseover = area.get("onmouseover", "")

    if not onmouseover.startswith("javascript:viewPoint("):
      continue

    # viewPoint(...) の中身を取り出す
    match = re.search(r"viewPoint\((.*)\)", onmouseover)

    if not match:
      continue

    args = re.findall(r"'([^']*)'", match.group(1))

    # 必要な項目数が取れていなければ無視
    if len(args) < 15:
      continue

    # JMA側の地点識別 s: 地上気象観測 / a: 地域気象観測(アメダス)
    station_type = args[0]
    # DL時、渡すコード値
    block_no = args[1]
    # 観測地点名
    name = re.split(r"[（(]", args[2])[0]
    # 観測地点カナ
    kana = args[3]
    # 緯度
    lat_deg = float(args[4])
    lat_min = float(args[5])
    # 経度
    lon_deg = float(args[6])
    lon_min = float(args[7])
    # 標高
    elevation = float(args[8])

    # 区分(除外処理用)
    flags = args[9:15]

    # station_typeによってstart_dateを設定
    if station_type == "s":
      start_date = date(1873, 1, 1)
    elif station_type == "a":
      start_date = date(1976, 1, 1)
    else:
      start_date = date(2001, 1, 1)

    # end_date設定
    end_date_year = int(args[15])
    end_date_month = int(args[16])
    end_date_day = int(args[17])
    if args[15] == "9999":
      end_date = date(9999, 12, 31)
    else:
      end_date = date(end_date_year, end_date_month, end_date_day)

    # 区分より気温を計測していない地点を除外
    if flags[1:4] == ["0", "0", "0"]:
      continue

    # 同じ地点がmap上に複数回登場するため重複排除
    key = (station_type, block_no)

    if key in stations:
      continue

    stations[key] = {
      "station_type": station_type,
      "block_no": block_no,
      "name": name,
      "kana": kana,
      "latitude": lat_deg + lat_min / 60,
      "longitude": lon_deg + lon_min / 60,
      "elevation": elevation,
      "prefecture_name": prec_no["prefecture_name"],
      "prefecture_name_en": prec_no["prefecture_name_en"],
      "start_date": start_date,
      "end_date": end_date
    }

  return stations

def load_amdmaster(path, config, messages):
  path = Path(path)

  # ファイルがなければダウンロード
  if not path.exists():
    message = messages["amdmaster_not_found"].format(path=path)
    print(message)
    logging.info(message)

    try:
      response = requests.get(
        config["URL"]["amdmaster_url"],
        timeout=int(config["DOWNLOAD"]["request_timeout"])
      )
      response.raise_for_status()

      path.parent.mkdir(parents=True, exist_ok=True)

      with open(path, "wb") as f:
        f.write(response.content)

      logging.info(messages["amdmaster_download_done"])

    except requests.RequestException as e:
      raise RuntimeError(
        messages["amdmaster_download_failed"].format(url=config["URL"]["amdmaster_url"])
      ) from e

    except OSError as e:
      raise RuntimeError(
        messages["save_amdmaster_failed"]
      ) from e

  # amdmaster.index4を読み込む
  master = {}

  with open(path, encoding=config["CSV"]["input_encoding"], newline="") as f:
    reader = csv.reader(f)

    # ヘッダー2行をスキップ
    next(reader)
    next(reader)

    for row in reader:
      if len(row) < 25:
        continue

      name = row[1].strip()
      name_en = row[3].strip().lower().replace("-", "")

      if not name:
        continue

      master[name] = {
        "name_en": name_en
      }

  return master

# --------------------
# 地点マスタDB登録
# --------------------
def save_location_master(all_stations, config, messages):
  sql = """
    INSERT INTO locations (
      station_type,
      block_no,
      name,
      kana,
      latitude,
      longitude,
      elevation,
      name_en,
      prefecture_name,
      prefecture_name_en,
      start_date,
      end_date
    )
    VALUES (
      %(station_type)s,
      %(block_no)s,
      %(name)s,
      %(kana)s,
      %(latitude)s,
      %(longitude)s,
      %(elevation)s,
      %(name_en)s,
      %(prefecture_name)s,
      %(prefecture_name_en)s,
      %(start_date)s,
      %(end_date)s
    )
    ON CONFLICT (station_type, block_no)
    DO UPDATE SET
      name = EXCLUDED.name,
      kana = EXCLUDED.kana,
      latitude = EXCLUDED.latitude,
      longitude = EXCLUDED.longitude,
      elevation = EXCLUDED.elevation,
      name_en = EXCLUDED.name_en,
      prefecture_name = EXCLUDED.prefecture_name,
      prefecture_name_en = EXCLUDED.prefecture_name_en,
      end_date = EXCLUDED.end_date;
  """
  try:
    with get_connection(config) as conn:
      with conn.cursor() as cur:
        for station in all_stations.values():
          cur.execute(sql, station)

    message = messages["set_locations_done"].format(count=len(all_stations))
    print(message)
    logging.info(message)

  except psycopg.Error as e:
    raise RuntimeError(messages["set_locations_failed"]) from e

# DB登録前の地点マスタ不正値チェック
def validate_stations(all_stations, messages):
  required_keys = [
    "station_type",
    "block_no",
    "name",
    "kana",
    "latitude",
    "longitude",
    "elevation",
    "name_en",
    "prefecture_name",
    "prefecture_name_en",
    "start_date",
    "end_date"
  ]

  errors = []

  for station in all_stations.values():
    missing_keys = [
      key for key in required_keys
      if key not in station
    ]

    if missing_keys:
      errors.append(
        f"{station.get('name')} "
        f"{station.get('block_no')} "
        f"不足項目: {missing_keys}"
      )

  if errors:
    raise ValueError(
      messages["locations_validate_error"].format(errors="\n".join(errors))
    )


# --------------------
# main処理
# --------------------
def main():
  config = load_config()
  message_config = load_message_config(config)
  messages = message_config["make_locations"]

  logging.basicConfig(
    filename=config["LOG"]["log_file"],
    level=logging.INFO,
    encoding=config["LOG"]["log_encoding"],
    format="%(asctime)s %(levelname)s [%(filename)s] %(message)s"
  )

  input_dir = (BASE_DIR / config["PATH"]["input_dir"])
  prec_no_file = (input_dir / config["FILE"]["prec_no"])
  amdmaster_file = (input_dir / config["FILE"]["amdmaster"])

  all_stations = {}

  logging.info("========== START ==========")

  try:
    reader = get_prec_no(prec_no_file, messages)
    logging.info(messages["get_prec_no"].format(path=prec_no_file))

    # locations登録のための地点情報を取得
    for row in reader:
        prec_no = row["prec_no"]
        prefecture_name = row["prefecture_name"]

        stations = get_stations(row, config)
        
        message = messages["get_stations"].format(
          prec_no=prec_no,
          prefecture_name=prefecture_name,
          count=len(stations)
        )
        print(message)
        logging.info(message)

        for key, station in stations.items():
          all_stations[key] = station
    
    amdmaster = load_amdmaster(amdmaster_file, config, messages)

    for station in all_stations.values():
      name = station["name"]

      if name in amdmaster:
        station["name_en"] = amdmaster[name]["name_en"]
      else:
        station["name_en"] = None

    # DB登録前に必須項目の格納チェック
    validate_stations(all_stations, messages)
    save_location_master(all_stations, config, messages)

  except (FileNotFoundError, RuntimeError, ValueError) as e:
    logging.error(str(e))
    print(f"エラー: {e}")
    sys.exit(1)

  finally:
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()
