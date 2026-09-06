import re
import requests
import csv
from bs4 import BeautifulSoup

BASE_URL = "https://www.data.jma.go.jp/stats/etrn/select/prefecture.php"



def get_stations(prec_no, prefecture):
  params = {
    "prec_no": prec_no,
    "block_no": "",
    "year": "",
    "month": "",
    "day": "",
    "view": "",
  }

  response = requests.get(BASE_URL, params=params, timeout=30)
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
      start_date = "9999-99-99"

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
      "prefecture": prefecture,
      "start_date": start_date
    }

  return stations

def load_amdmaster(path):
  master = {}

  with open(path, encoding="shift_jis", newline="") as f:
    reader = csv.reader(f)

    # ヘッダー2行をスキップ
    next(reader)
    next(reader)

    for row in reader:
      if len(row) < 25:
        continue

      name = row[1].strip()
      name_en = row[3].strip().lower()
      end_date = row[24].strip()

      if not name:
        continue

      master[name] = {
        "name_en": name_en,
        "end_date": end_date
      }

  return master


def main():
  all_stations = {}
  with open("prec_no.csv", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)

    for row in reader:
      prec_no = row["番号"]
      prefecture = row["府県名"]
      print(f"\n===== prec_no={prec_no} =====")

      stations = get_stations(prec_no, prefecture)

      for key, station in stations.items():
        all_stations[key] = station

  amdmaster = load_amdmaster("amdmaster.index4")

  for station in all_stations.values():
    name = station["name"]

    if name in amdmaster:
      station["name_en"] = amdmaster[name]["name_en"]
      station["end_date"] = amdmaster[name]["end_date"]


  with open("location.csv", "w", encoding="utf-8-sig", newline="") as f:
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
        "prefecture",
        "start_date",
        "end_date"
      ]
    )
    writer.writeheader()
    writer.writerows(all_stations.values())

if __name__ == "__main__":
  main()
