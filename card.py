import configparser
import logging
import json
import sys
from pathlib import Path
import pandas as pd

# --------------------
# 設定ファイル
# --------------------

# config.iniの取得
def load_config():
  config = configparser.ConfigParser()

  config.read(
    "config.ini",
    encoding="utf-8"
  )

  return config

# item_config.jsonの取得
def load_item(config):
  input_dir = Path(config["PATH"]["input_dir"])
  filename = (input_dir / "item_config.json")

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
def create_html(csv_file, config):
  # 地点マスタのパス設定
  location_dir = Path(config["PATH"]["location_input_dir"])
  location_file = (location_dir / "locations.csv")
  try:
    # CSV読み込み
    location_df = pd.read_csv(
      location_file, dtype={"block_no": str},
      encoding=config["CSV"]["output_encoding"]
    )
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
    <title>{display_date} {location_name["name"]}</title>
    <link rel="stylesheet" href="../style.css">
  </head>

  <body>
    <h1>{display_date} {location_name["name"]}</h1>
  """
  for comparison, group in groups:
    html += f"""
    <div class="weather-card">
      <h2>{comparison}</h2>
    """

    # CSVの各行からカードを作成
    for i, (_, row) in enumerate(group.iterrows()):
      item = row["項目"]
      actual = format_value(row["実測値"])
      location_avg = format_value(row["地点基準値"])
      location_diff = format_diff(row["差(地点)"])
      overall_avg = format_value(row["全体基準値"])
      overall_diff = format_diff(row["差(全体)"])
      location_score = int(row["地点スコア"])
      overall_score = int(row["全体スコア"])

      actual_color = score_to_color(location_score, item_config[item])
      location_score_color = score_to_color(location_score, item_config[item])
      overall_score_color = score_to_color(overall_score, item_config[item])
      # TODO ここは応急処置なので後で修正予定
      location_diff_color = diff_to_color(float(row["差(地点)"]))
      overall_diff_color = diff_to_color(float(row["差(全体)"]))

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
          <span class="cold">{item_config[item]["low_label"]}</span>

          <div class="bar">
            <div class="bar-fill"
              style="width: {location_score}%; background-color: {location_score_color};"></div>
            <span class="marker"
              style="left: {location_score}%; background-color: {location_score_color};">
              {location_score}
            </span>
          </div>

          <span class="hot">{item_config[item]["high_label"]}</span>
        </div>

        <div class="score-row">
          <span class="score-label">全体</span>
          <span class="cold">{item_config[item]["low_label"]}</span>
          <div class="bar">
            <div class="bar-fill"
              style="width: {overall_score}%; background-color: {overall_score_color};"></div>
            <span class="marker"
              style="left: {overall_score}%; background-color: {overall_score_color};">
              {overall_score}
            </span>
          </div>
          <span class="hot">{item_config[item]["high_label"]}</span>
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
  output_file = csv_file.with_suffix(".html")
  output_file.write_text(html, encoding="utf-8")

  print(f"生成: {output_file}")
  logging.info(f"生成: {output_file}")


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

  input_dir = Path(config["PATH"]["result_dir"])

  logging.info("========== START ==========")

  # --------------------
  # 各CSVをHTMLに変換
  # --------------------
  try:
    csv_files = load_result_csv_files(input_dir)

    for csv_file in csv_files:
      create_html(csv_file, config)

    logging.info("HTML出力完了")

  except (FileNotFoundError, ValueError) as e:
    logging.error(str(e))
    print(f"エラー: {e}")
    sys.exit(1)

  finally:
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()