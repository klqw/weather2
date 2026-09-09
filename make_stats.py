import configparser
import logging
import sys
from pathlib import Path
import pandas as pd

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
# 全地点の元データ取得
# --------------------
def load_csv_files(data_dir, config):

  files = list(data_dir.glob("*.csv"))

  if not files:
    raise FileNotFoundError("CSVファイルがありません")

  dfs = []

  for file in files:
    logging.info("読み込み: %s", file)

    # ファイル名からlocation, codeを取得
    location = file.name.split("_")[0]
    code = file.name.split("_")[1]

    usecols_map = {
      "s": [0, 1, 5, 8, 11, 14, 17, 21, 25],
      "a": [0, 1, 4, 7, 10, 13, 16, 19, 22]
    }
    usecols = usecols_map[code[0]]
    
    df = pd.read_csv(
      file,
      encoding=config["CSV"]["input_encoding"],
      skiprows=[0, 1, 2, 4, 5],
      usecols=usecols
    )

    # location, codeカラムを追加
    df["location"] = location
    df["code"] = code

    dfs.append(df)

  return pd.concat(dfs, ignore_index=True)


# --------------------
# データいじり
# --------------------

# 年月日の前処理 (datetimeに変換 -> 月, 日を作成)
def prepare_date(df):
  df = df.copy()

  df["年月日"] = pd.to_datetime(
    df["年月日"],
    format="%Y/%m/%d"
  )
  df["月"] = df["年月日"].dt.month
  df["日"] = df["年月日"].dt.day

  return df

# 表示項目をまとめる
def get_weather_columns(config):
  return [
    config["COLUMN"]["avg_tmp"],      # 平均気温(℃)
    config["COLUMN"]["max_tmp"],      # 最高気温(℃)
    config["COLUMN"]["min_tmp"],      # 最低気温(℃)
    config["COLUMN"]["precip"],       # 降水量の合計(mm)
    config["COLUMN"]["avg_wind"],     # 平均風速(m/s)
    config["COLUMN"]["sunshine"],     # 日照時間(時間)
    config["COLUMN"]["max_snow"],     # 最深積雪(cm)
    config["COLUMN"]["avg_humidity"]  # 平均湿度(％)
  ]

# locationごと & 月ごとの平均気温を全取得
def location_month_avg(df, config):
  return (
    df.groupby(["location", "code", "月"])[
      get_weather_columns(config)
    ].mean().reset_index()
  )

# locationごと & 月・日ごとの平均気温を全取得
def location_daily_avg(df, config):
  return (
    df.groupby(["location", "code", "月", "日"])[
      get_weather_columns(config)
    ].mean().reset_index()
  )

# locationごと & 全期間の平均気温を取得
def location_overall_avg(df, config):
  return (
    df.groupby(["location", "code"])[
      get_weather_columns(config)
    ].mean().reset_index()
  )

# locationごと & 月・日ごとの各気温の最高値を全取得
def location_daily_max(df, config):
  return (
    df.groupby(["location", "code", "月", "日"])[
      get_weather_columns(config)
    ].max().reset_index()
  )

# locationごと & 月・日ごとの各気温の最低値を全取得
def location_daily_min(df, config):
  return (
    df.groupby(["location", "code", "月", "日"])[
      get_weather_columns(config)
    ].min().reset_index()
  )

# --------------------
# CSV出力
# --------------------

# 整えたフォーマットをCSVで出力
def save_csv(df, output_file, config):
  try:
    output_file.parent.mkdir(
      parents=True,
      exist_ok=True
    )

    df.to_csv(
      output_file,
      index=False,
      encoding=config["CSV"]["output_encoding"]
    )

  except OSError as e:
    raise RuntimeError(f"CSVの出力に失敗しました: {output_file}") from e


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

  input_dir = Path(config["PATH"]["data_dir"])
  output_dir = Path(config["PATH"]["output_dir"])

  logging.info("========== START ==========")

  try:
    # --------------------
    # CSV読み込み
    # --------------------
    df = load_csv_files(input_dir, config)
    logging.info("CSV読み込み完了")

    # --------------------
    # データ加工
    # --------------------

    # 日付関連の前処理
    df = prepare_date(df)

    # 月ごと、日ごと、全期間の平均値比較結果を取得
    month_stats = location_month_avg(df, config)
    # print(month_stats)

    daily_stats = location_daily_avg(df, config)
    # print(daily_stats)

    overall_stats = location_overall_avg(df, config)
    # print(overall_stats)

    # locationごと & 月・日ごとの各気温の最高値を全取得
    daily_max_stats = location_daily_max(df, config)

    # locationごと & 月・日ごとの各気温の最低値を全取得
    daily_min_stats = location_daily_min(df, config)

    # --------------------
    # 出力
    # --------------------

    # 出力ファイル名指定
    month_filename = "month_stats.csv"
    daily_filename = "daily_stats.csv"
    all_filename = "overall_stats.csv"
    max_filename = "max_stats.csv"
    min_filename = "min_stats.csv"

    # 出力ファイルパス指定
    month_output_file = (output_dir / config["PATH"]["stats_dir"] / month_filename)
    daily_output_file = (output_dir / config["PATH"]["stats_dir"] / daily_filename)
    all_output_file = (output_dir / config["PATH"]["stats_dir"] / all_filename)
    max_output_file = (output_dir / config["PATH"]["stats_dir"] / max_filename)
    min_output_file = (output_dir / config["PATH"]["stats_dir"] / min_filename)

    # 月、月・日、全期間のCSV出力
    save_csv(month_stats, month_output_file, config)
    save_csv(daily_stats, daily_output_file, config)
    save_csv(overall_stats, all_output_file, config)
    save_csv(daily_max_stats, max_output_file, config)
    save_csv(daily_min_stats, min_output_file, config)
    print(f"\n月ごとのCSV出力先: {month_output_file}")
    print(f"月・日ごとのCSV出力先: {daily_output_file}")
    print(f"全期間のCSV出力先: {all_output_file}")
    print(f"最高値のCSV出力先: {max_output_file}")
    print(f"最低値のCSV出力先: {min_output_file}")
    logging.info("出力完了(month): %s", month_output_file)
    logging.info("出力完了(daily): %s", daily_output_file)
    logging.info("出力完了(overall): %s", all_output_file)
    logging.info("出力完了(max): %s", max_output_file)
    logging.info("出力完了(min): %s", min_output_file)

  except (FileNotFoundError, RuntimeError) as e:
    logging.error(str(e))
    print(f"エラー: {e}")
    sys.exit(1)

  finally:
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()