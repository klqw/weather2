import configparser
import re
import requests
import csv
import logging
import sys
from pathlib import Path
from bs4 import BeautifulSoup

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
# 地点マスタ生成のための情報取得
# --------------------
def get_prec_no(input_file):
  try:
    with open(input_file, encoding="utf-8", newline="") as f:
      reader = csv.DictReader(f)
      return list(reader)

  except FileNotFoundError:
    raise FileNotFoundError("prec_no参照CSVがありません: %s", input_file)

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
      start_date = "1873-01-01"
    elif station_type == "a":
      start_date = "1976-01-01"
    else:
      start_date = "2001-01-01"

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
      "start_date": start_date
    }

  return stations

def load_amdmaster(path, config):
  path = Path(path)

  # ファイルがなければダウンロード
  if not path.exists():
    print(f"amdmaster.index4が見つからないため、ダウンロードします: {path}")
    logging.info("amdmaster.index4が見つからないため、ダウンロードします: %s", path)

    try:
      response = requests.get(
        config["URL"]["amdmaster_url"],
        timeout=int(config["DOWNLOAD"]["request_timeout"])
      )
      response.raise_for_status()

      path.parent.mkdir(parents=True, exist_ok=True)

      with open(path, "wb") as f:
        f.write(response.content)

      logging.info("amdmaster.index4のダウンロード完了")

    except requests.RequestException as e:
      raise RuntimeError(
        f"amdmaster.index4のダウンロードに失敗しました: {config["URL"]["amdmaster_url"]}"
      ) from e

    except OSError as e:
      raise RuntimeError(
        "amdmaster.index4の保存に失敗しました"
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
      end_date = row[24].strip()

      if not name:
        continue

      master[name] = {
        "name_en": name_en,
        "end_date": end_date
      }

  return master

# --------------------
# 地点マスタ出力
# --------------------
def save_location_master(output_file, all_stations, config):
  try:
    with open(output_file, "w", encoding=config["CSV"]["output_encoding"], newline="") as f:
      writer = csv.DictWriter(
        f,
        fieldnames=[
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
      )

      writer.writeheader()
      writer.writerows(all_stations.values())

  except OSError as e:
    raise RuntimeError(f"地点マスタのCSV出力に失敗しました: {output_file}") from e


# --------------------
# main処理
# --------------------
def main():
  config = load_config()

  logging.basicConfig(
    filename=config["LOG"]["log_file"],
    level=logging.INFO,
    encoding=config["LOG"]["log_encoding"],
    format="%(asctime)s %(levelname)s [%(filename)s] %(message)s"
  )

  input_dir = Path(config["PATH"]["input_dir"])
  output_dir = Path(config["PATH"]["location_dir"])

  prec_no_file = (input_dir / "prec_no.csv")
  amdmaster_file = (input_dir / "amdmaster.index4")
  locations_file = (output_dir / "locations.csv")

  all_stations = {}

  logging.info("========== START ==========")

  try:
    reader = get_prec_no(prec_no_file)
    logging.info("prec_no参照CSV読み込み完了: %s", prec_no_file)

    for row in reader:
        prec_no = row["prec_no"]
        prefecture_name = row["prefecture_name"]

        stations = get_stations(row, config)
        print(f"prec_no: {prec_no} prefecture_name: {prefecture_name} を取得 ({len(stations)}地点)")
        logging.info(
          "prec_no: %s prefecture_name: %s を取得 (%d地点)",
          prec_no, prefecture_name, len(stations)
        )

        for key, station in stations.items():
          all_stations[key] = station
    
    amdmaster = load_amdmaster(amdmaster_file, config)

    for station in all_stations.values():
      name = station["name"]

      if name in amdmaster:
        station["name_en"] = amdmaster[name]["name_en"]
        station["end_date"] = amdmaster[name]["end_date"]

    save_location_master(locations_file, all_stations, config)
    print(f"\n出力先: {locations_file}")
    logging.info("出力完了: %s", locations_file)

  except (FileNotFoundError, RuntimeError) as e:
    logging.error(str(e))
    print(f"エラー: {e}")
    sys.exit(1)

  finally:
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()
