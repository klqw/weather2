import configparser
import html
import re
from pathlib import Path
from db import get_connection

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config" / "config.ini"

# Cardを格納しているディレクトリ
CARD_DIR = BASE_DIR / "output" / "card"

# 出力先ディレクトリ
OUT_DIR = BASE_DIR / "output"

CARD_PATTERN = re.compile(
  r"^(?P<name_en>.+)_(?P<station_type>[as])(?P<block_no>\d+)_(?P<date>\d{8})\.html$"
)

# --------------------
# 設定ファイル
# --------------------
def load_config():
  config = configparser.ConfigParser()
  config.read(CONFIG_FILE, encoding="utf-8")
  return config

def get_locations(config):
  sql = """
    SELECT
      station_type,
      block_no,
      name,
      prefecture_name
    FROM locations;
  """

  with get_connection(config) as conn:
    with conn.cursor() as cur:
      cur.execute(sql)
      rows = cur.fetchall()

  return {
    (row[0], str(row[1])): {
      "name": row[2],
      "prefecture_name": row[3]
    }
    for row in rows
  }


def get_cards(card_dir, locations):
  cards = []

  for file_path in card_dir.glob("*.html"):
    if file_path.name == "index.html":
      continue

    match = CARD_PATTERN.match(file_path.name)

    if not match:
      continue

    station_type = match.group("station_type")
    block_no = match.group("block_no")
    yyyymmdd = match.group("date")

    location = locations.get((station_type, block_no))

    if location is None:
      print(f"地点マスタに存在しません: {file_path.name}")
      continue

    cards.append({
      "filename": file_path.name,
      "name": location["name"],
      "prefecture_name": location["prefecture_name"],
      "date": yyyymmdd
    })

  return sorted(
    cards,
    key=lambda x: (
      x["prefecture_name"],
      x["name"],
      x["date"]
    )
  )


def format_date(yyyymmdd):
  return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def make_index(cards):
  links = []

  for card in cards:
    filename = html.escape(card["filename"])
    prefecture_name = html.escape(card["prefecture_name"])
    name = html.escape(card["name"])
    date_text = format_date(card["date"])

    links.append(
      f'    <li><a href="card/{filename}">'
      f'{prefecture_name} {name} - {date_text}'
      f'</a></li>'
    )

  link_html = "\n".join(links)

  return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Weather Cards</title>
</head>
<body>
  <h1>Weather Cards</h1>
  <ul>
{link_html}
  </ul>
</body>
</html>
"""


# --------------------
# main処理
# --------------------
def main():
  config = load_config()

  locations = get_locations(config)
  cards = get_cards(CARD_DIR, locations)

  index_html = make_index(cards)

  output_file = OUT_DIR / "index.html"
  output_file.write_text(index_html, encoding="utf-8")

  print(f"index.htmlを生成しました: {output_file}")
  print(f"Card件数: {len(cards)}件")


if __name__ == "__main__":
  main()