import configparser
import logging
import json
import sys
from pathlib import Path
import pandas as pd
import psycopg
from db import get_connection
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config" / "config.ini"

# --------------------
# 設定ファイル
# --------------------

# config.iniの取得
def load_config():
  config = configparser.ConfigParser()
  config.read(CONFIG_FILE, encoding="utf-8")
  return config

# item_config.jsonの取得
def load_item(config):
  filename = (
    BASE_DIR / config["PATH"]["config_dir"] / config["FILE"]["items"]
  )

  try:
    with open(filename, encoding="utf-8") as f:
      item_config = json.load(f)

  except FileNotFoundError:
    raise FileNotFoundError(f"JSONファイルがありません: {filename}")

  if not item_config:
    raise ValueError(f"JSONファイルの内容が空です: {filename}")

  return item_config


# --------------------
# CSV -> HTML
# --------------------

# locationsから地点マスタ取得
def get_locations(config):
  sql = """
    SELECT
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
    FROM locations;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        location_data = cur.fetchall()

        if location_data is None:
          raise ValueError("locationsテーブルにデータがありませんでした")

        logging.info("locationsテーブルからの取得に成功しました")

        return location_data

  except psycopg.Error as e:
    raise RuntimeError("locationsテーブルからの取得に失敗しました") from e


# output/result からCSVを取得
def load_result_csv_files(result_dir):
  csv_files = list(result_dir.glob("*.csv"))

  if not csv_files:
    raise FileNotFoundError("CSVファイルがありません")

  return csv_files

# NaN値の場合、「－」に置換
def format_value(value):
  return "－" if pd.isna(value) else value

def format_diff(value):
  if pd.isna(value):
    return "－"
  return f"{value:+.1f}"

# 色変換 HEX -> RGB
def hex_to_rgb(hex_color):
  r = int(hex_color[1:3], 16)
  g = int(hex_color[3:5], 16)
  b = int(hex_color[5:7], 16)

  return r, g, b

# スコアによってバッジの表示/非表示を設定
def make_score_marker(score, color):
  if score == 0:
    return ""

  return f"""
    <span class="marker"
      style="left: {score}%; background-color: {color};">
      {score}
    </span>
  """

# スコアごとにマーカーとバッジの背景色設定
def score_to_color(score, item_config):
  """
  スコア 1～100を
  青 → 水色 → 緑 → オレンジ → 赤
  のようにグラデーションに変換する
  """
  # 色の基準設定(HEX)
  colors = item_config["colors"]
  # RGBに変換
  colors = [hex_to_rgb(color) for color in colors]

  # スコア 1～100 → 0～4 に変換
  score = max(1, min(100, score))
  position = (score - 1) / 99 * 4
  index = int(position)

  # 100点の場合
  if index >= 4:
    r, g, b = colors[4]
    return f"rgb({r}, {g}, {b})"

  # グラデーション設定
  ratio = position - index
  r1, g1, b1 = colors[index]
  r2, g2, b2 = colors[index + 1]

  # RGB値計算
  r = round(r1 + (r2 - r1) * ratio)
  g = round(g1 + (g2 - g1) * ratio)
  b = round(b1 + (b2 - b1) * ratio)

  return f"rgb({r}, {g}, {b})"

# 差分の文字色設定
def diff_to_color(diff):
  if diff > 0.0:
    color = "positive"
  elif diff < 0.0:
    color = "negative"
  else:
    color = "zero"

  return color

# CSV -> HTML
def create_html(location_df, csv_file, output_dir, config):
  try:
    # CSV読み込み
    output_df = pd.read_csv(csv_file)

  except FileNotFoundError as e:
    print(f"エラー: {e}")
    raise FileNotFoundError("CSVファイルがありません")

  groups = output_df.groupby("比較対象", sort=False)

  # ファイル名から地点コード・日付を取得
  _, location_code, date = csv_file.stem.split("_")
  station_type = location_code[0]
  block_no = location_code[1:]

  # 地点名取得
  location_rows = location_df.loc[
    (location_df["station_type"] == station_type) &
    (location_df["block_no"] == block_no),
    ["name", "prefecture_name"]
  ]

  if location_rows.empty:
    raise ValueError(f"地点マスタに存在しません (地点コード: {location_code})")
  location_name = location_rows.iloc[0]

  # 日付を表示用に変換
  display_date = (
    f"{date[:4]}年{int(date[4:6])}月{int(date[6:8])}日"
  )

  # HTML生成用のitemを取得
  item_config = load_item(config)

  # HTML生成
  html = f"""<!DOCTYPE html>
  <html lang="ja">
  <head>
    <meta charset="UTF-8">
    <title>{display_date} {location_name["name"]} - {location_name["prefecture_name"]}</title>
    <link rel="stylesheet" href="../style.css">
  </head>

  <body>
    <header class="header">
      <h1>{display_date} {location_name["name"]} - {location_name["prefecture_name"]}</h1>
    </header>
  """
  for comparison, group in groups:
    html += f"""
    <div class="weather-card">
      <h2>{comparison}</h2>
    """

    # CSVの各行からカードを作成
    for i, (_, row) in enumerate(group.iterrows()):
      # HTML表示用(文字列)
      item = row["項目"]
      actual = format_value(row["実測値"])
      location_avg = format_value(row["地点基準値"])
      location_diff = format_diff(row["差(地点)"])
      overall_avg = format_value(row["全体基準値"])
      overall_diff = format_diff(row["差(全体)"])
      location_score = int(row["地点スコア"])
      overall_score = int(row["全体スコア"])

      # HTML表示用(色)
      actual_color = score_to_color(location_score, item_config[item])
      location_score_color = score_to_color(location_score, item_config[item])
      overall_score_color = score_to_color(overall_score, item_config[item])

      location_diff_color = diff_to_color(float(row["差(地点)"]))
      overall_diff_color = diff_to_color(float(row["差(全体)"]))

      # Low, Highラベル色設定
      low_label_color = item_config[item]["colors"][0]
      high_label_color = item_config[item]["colors"][4]

      # マーカーに表示するバッジの設定
      location_marker = make_score_marker(location_score, location_score_color)
      overall_marker = make_score_marker(overall_score, overall_score_color)

      html += f"""

      <h3>{item}</h3>

      <div class="actual">
        実測値 <strong style="color: {actual_color};">{actual}{item_config[item]["unit"]}</strong>
      </div>
      
      <div class="averages">
        <span>地点平均 {location_avg}{item_config[item]["unit"]}</span>
        <span>全体平均 {overall_avg}{item_config[item]["unit"]}</span>
      </div>

      <div class="differences">
        <span>地点平均との差 
          <span class="{location_diff_color}">{location_diff}{item_config[item]["unit"]}</span>
        </span>
        <span>全体平均との差 
          <span  class="{overall_diff_color}">{overall_diff}{item_config[item]["unit"]}</span>
        </span>
      </div>

      <div class="score-group">

        <div class="score-row">
          <span class="score-label">地点</span>
          <span class="low" style="color: {low_label_color};">
            {item_config[item]["low_label"]}
          </span>

          <div class="bar">
            <div class="bar-fill"
              style="width: {location_score}%; background-color: {location_score_color};"></div>
            {location_marker}
          </div>

          <span class="high" style="color: {high_label_color};">
            {item_config[item]["high_label"]}
          </span>
        </div>

        <div class="score-row">
          <span class="score-label">全体</span>
          <span class="low" style="color: {low_label_color};">
            {item_config[item]["low_label"]}
          </span>

          <div class="bar">
            <div class="bar-fill"
              style="width: {overall_score}%; background-color: {overall_score_color};"></div>
            {overall_marker}
          </div>

          <span class="high" style="color: {high_label_color};">
            {item_config[item]["high_label"]}
          </span>
        </div>

      </div>
      """
      if i != len(group) - 1:
        html += """
      <hr>
        """

    html += """
    </div>
    """
  html += """
  </body>
  </html>
  """

  # HTML出力
  output_file = output_dir / f"{csv_file.stem}.html"
  output_file.write_text(html, encoding="utf-8")

  print(f"生成: {output_file}")
  logging.info(f"生成: {output_file}")


# --------------------
# main処理
# --------------------
def main():
  config = load_config()

  # ログ設定
  log_file = Path(config["LOG"]["log_file"])
  log_file.parent.mkdir(parents=True, exist_ok=True)
  logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    encoding=config["LOG"]["log_encoding"],
    format="%(asctime)s %(levelname)s [%(filename)s] %(message)s"
  )

  input_dir = Path(config["PATH"]["result_dir"])
  output_dir = Path(config["PATH"]["card_dir"])

  output_dir.mkdir(parents=True, exist_ok=True)

  logging.info("========== START ==========")

  # --------------------
  # 各CSVをHTMLに変換
  # --------------------
  try:
    # 地点マスタ取得
    location_df = pd.DataFrame(get_locations(config))

    csv_files = load_result_csv_files(input_dir)

    for csv_file in csv_files:
      create_html(location_df, csv_file, output_dir, config)

    logging.info("HTML出力完了")

  except (FileNotFoundError, ValueError) as e:
    logging.error(str(e))
    print(f"エラー: {e}")
    sys.exit(1)

  finally:
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()