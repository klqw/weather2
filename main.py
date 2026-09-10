import argparse
import configparser
import logging
import csv
import sys
from pathlib import Path
import pandas as pd
import numpy as np

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

def load_csv_files(data_dir, location_code, config):

  files = list(data_dir.glob(f"*_{location_code}_*.csv"))

  if not files:
    raise FileNotFoundError("CSVファイルがありません")

  dfs = []

  for file in files:
    logging.info("読み込み: %s", file)

    # 気象台, アメダスそれぞれの使用カラム指定
    usecols_map = {
      "s": [0, 1, 5, 8, 11, 14, 17, 21, 25],
      "a": [0, 1, 4, 7, 10, 13, 16, 19, 22]
    }
    usecols = usecols_map[location_code[0]]

    df = pd.read_csv(
      file,
      encoding=config["CSV"]["input_encoding"],
      skiprows=[0, 1, 2, 4, 5],
      usecols=usecols
    )
    dfs.append(df)

  return pd.concat(dfs, ignore_index=True)


# --------------------
# argバリデーション
# --------------------

# location, prefecture
def validate_location(location, prefecture, config):
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

  if len(matches) != 1:
    raise ValueError(
      f"地点名と都府県名の組み合わせが不正です 地点名: {location}, 都府県名: {prefecture}"
    )
  
  # 取得対象が1件だった場合は取得対象地点のstationNumを返す
  logging.info("取得対象 地点名: %s, 都府県名: %s", location, prefecture)
  return matches[0]["station_type"] + matches[0]["block_no"]

# date
def validate_date(df, date):
  try:
    target_date = pd.to_datetime(
      date,
      format="%Y%m%d"
    )
  except ValueError:
    raise ValueError(f"不正なdateです: {date}")

  if not df["年月日"].eq(target_date).any():
    raise ValueError(
      f"指定されたdateのデータがありません: {date}"
    )

  return target_date

# --------------------
# データいじり
# --------------------

# 年月日をdatetimeに変換
def prepare_date(df):
  df = df.copy()

  df["年月日"] = pd.to_datetime(
    df["年月日"],
    format="%Y/%m/%d"
  )
  df["月"] = df["年月日"].dt.month
  df["日"] = df["年月日"].dt.day

  return df

# 表示項目の設定
def get_temp_columns(config):
  return [
    config["COLUMN"]["avg_tmp"],      # 平均気温(℃)
    config["COLUMN"]["max_tmp"],      # 最高気温(℃)
    config["COLUMN"]["min_tmp"],      # 最低気温(℃)
    config["COLUMN"]["avg_humidity"], # 平均湿度(％)
    config["COLUMN"]["sunshine"],     # 日照時間(時間)
    config["COLUMN"]["precip"],       # 降水量の合計(mm)
    config["COLUMN"]["avg_wind"],     # 平均風速(m/s)
    config["COLUMN"]["max_snow"]      # 最深積雪(cm)
  ]

# 差分の計算(NaN値対策)
def calc_diff(actual, base):
  result = actual.copy()

  for column in actual.index:
    if pd.isna(actual[column]) or pd.isna(base[column]):
      result[column] = np.nan

    else:
      result[column] = actual[column] - base[column]

  return result

# スコアの計算(NaN値対策)
def calc_score(base_value, max_value, min_value):
  result = base_value.copy()

  for column in base_value.index:
    if pd.isna(base_value[column]) or pd.isna(max_value[column]) or pd.isna(min_value[column]):
      result[column] = 0

    else:
      result[column] = (base_value[column] - min_value[column]) / (max_value[column] - min_value[column]) * 99 + 1

  return result

# スコア計算時のラベル(カラム名)を設定
def get_score_calc_columns(config):
  return {
    "loc_day": config["COLUMN"]["location_daily_score"],
    "loc_mon": config["COLUMN"]["location_month_score"],
    "loc_all": config["COLUMN"]["location_overall_score"],
    "all_day": config["COLUMN"]["all_daily_score"],
    "all_mon": config["COLUMN"]["all_month_score"],
    "all_all": config["COLUMN"]["all_overall_score"]
  }

# スコア出力時のラベル(カラム名)を設定
def get_score_out_columns(config):
  return [
    config["COLUMN"]["output_location_score"],
    config["COLUMN"]["output_all_score"]
  ]

# 日ごと、月ごと、全期間に合わせてスコアを格納
def extract_score(score, label, period, config):
  columns = {
    "daily": [label["loc_day"], label["all_day"]],  # 日ごと
    "month": [label["loc_mon"], label["all_mon"]],  # 月ごと
    "overall": [label["loc_all"], label["all_all"]] # 全期間
  }

  if period not in columns:
    raise ValueError(f"不正な期間です: {period}")

  result = score[columns[period]].copy()
  result.columns = get_score_out_columns(config)
  # print(result)

  return result

# make_statsからの取得
def get_stats(input_file, config):

  try:
    stats = pd.read_csv(
      input_file,
      encoding=config["CSV"]["output_encoding"]
    )

  except FileNotFoundError:
    raise # main側で処理

  logging.info(f"Statsファイル読み込み完了: {input_file}")

  return stats

# 指定日の実測値を取得
def get_target_temp(df, target_date):
  return df[
    df["年月日"] == target_date
  ]

# --------------------
# 指定日付の差分分析
# --------------------

# 指定日と月ごとの比較
def month_diff(input_file, location, target_temp, config):
  # StatsのCSVファイルを取得
  df = get_stats(input_file, config)

  # 指定日の月を取得
  target_month = target_temp["年月日"].iloc[0].month

  # 指定日の月に対応する平均値を取得
  df = df[
    df["月"] == target_month
  ]

  # 全地点の指定日の月に対する平均値を取得
  all_avg = df.groupby(["location", "月"])[
    get_temp_columns(config)
  ].mean()
  all_avg = all_avg.mean().to_frame().T
  # print(all_avg)

  # ターゲット地点の指定日の月に対する平均値を取得
  target_avg = df[
    df["location"] == location
  ]
  # print(target_avg)

  # target_tempを比較用に加工
  actual = target_temp[
    get_temp_columns(config)
  ].iloc[0]

  # 全地点の指定日の月に対する平均値を比較用に加工
  base_all = all_avg[
    get_temp_columns(config)
  ].iloc[0]

  # ターゲット地点の指定日の月に対する平均値を比較用に加工
  base_target = target_avg[
    get_temp_columns(config)
  ].iloc[0]

  return pd.DataFrame({
    "実測値": actual,
    "地点基準値": base_target,
    "差(地点)": calc_diff(actual, base_target),
    "全体基準値": base_all,
    "差(全体)": calc_diff(actual, base_all)
  }).round(1)

# 指定日と日ごとの比較
def daily_diff(input_file, location, target_temp, config):
  # StatsのCSVファイルを取得
  df = get_stats(input_file, config)

  # 指定日の月・日を取得
  target_month = target_temp["年月日"].iloc[0].month
  target_day = target_temp["年月日"].iloc[0].day

  # 指定日の月・日に対する平均値を取得
  df = df[
    (df["月"] == target_month) &
    (df["日"] == target_day)
  ]

  # 全地点の指定日の月・日に対する平均値を取得
  all_avg = df.groupby(["location", "月", "日"])[
    get_temp_columns(config)
  ].mean()
  all_avg = all_avg.mean().to_frame().T
  # print(all_avg)

  # ターゲット地点の指定日の月・日に対する平均値を取得
  target_avg = df[
    df["location"] == location
  ]
  # print(target_avg)

  # target_tempを比較用に加工
  actual = target_temp[
    get_temp_columns(config)
  ].iloc[0]

  # 全地点の指定日の月・日に対する平均値を比較用に加工
  base_all = all_avg[
    get_temp_columns(config)
  ].iloc[0]

  # ターゲット地点の指定日の月・日に対する平均値を比較ように加工
  base_target = target_avg[
    get_temp_columns(config)
  ].iloc[0]

  return pd.DataFrame({
    "実測値": actual,
    "地点基準値": base_target,
    "差(地点)": calc_diff(actual, base_target),
    "全体基準値": base_all,
    "差(全体)": calc_diff(actual, base_all)
  }).round(1)

# 指定日と全期間の比較
def all_diff(input_file, location, target_temp, config):
  # StatsのCSVファイルを取得
  df = get_stats(input_file, config)
  # print(df)

  # 全地点の平均値を取得
  all_avg = df.mean(numeric_only=True).to_frame().T
  # print(all_avg)

  # ターゲット地点の平均値を取得
  target_avg = df[
    df["location"] == location
  ]
  # print(target_avg)

  # target_tempを比較用に加工
  actual = target_temp[
    get_temp_columns(config)
  ].iloc[0]

  # 全地点の平均値を比較用に加工
  base_all = all_avg[
    get_temp_columns(config)
  ].iloc[0]

  # ターゲット地点の平均値を比較用に加工
  base_target = target_avg[
    get_temp_columns(config)
  ].iloc[0]

  return pd.DataFrame({
    "実測値": actual,
    "地点基準値": base_target,
    "差(地点)": calc_diff(actual ,base_target),
    "全体基準値": base_all,
    "差(全体)": calc_diff(actual, base_all)
  }).round(1)
  
# 指定日の最大値と最小値からスコア計算したdfを出力
def make_score_df(max_input_file, min_input_file, location, target_temp, config):
  # Statsの最大値CSVファイルを取得
  max_df = get_stats(max_input_file, config)

  # Statsの最小値CSVファイルを取得
  min_df = get_stats(min_input_file, config)

  # 指定日の月・日を取得
  target_month = target_temp["年月日"].iloc[0].month
  target_day = target_temp["年月日"].iloc[0].day

  # 指定地点 & 指定日の最大値を取得
  max_location_daily_df = max_df[
    (max_df["location"] == location) &
    (max_df["月"] == target_month) &
    (max_df["日"] == target_day)
  ]
  # スコア計算用に加工
  max_loc_day = max_location_daily_df[
    get_temp_columns(config)
  ].iloc[0]

  # 指定地点 & 指定月の最大値を取得
  max_location_month_df = max_df[
    (max_df["location"] == location) &
    (max_df["月"] == target_month)
  ]
  # スコア計算用に加工
  max_loc_mon = max_location_month_df[
    get_temp_columns(config)
  ].max()

  # 指定地点 & 全期間の最大値を取得
  max_location_all_df = max_df[
    (max_df["location"] == location)
  ]
  # スコア計算用に加工
  max_loc_all = max_location_all_df[
    get_temp_columns(config)
  ].max()

  # 全地点 指定日の最大値を取得
  max_daily_df = max_df[
    (max_df["月"] == target_month) &
    (max_df["日"] == target_day)
  ]
  # スコア計算用に加工
  max_day = max_daily_df[
    get_temp_columns(config)
  ].max()

  # 全地点 & 指定月の最大値を取得
  max_month_df = max_df[
    (max_df["月"] == target_month)
  ]
  # スコア計算用に加工
  max_mon = max_month_df[
    get_temp_columns(config)
  ].max()

  # 全地点 & 全期間の最大値を取得、加工
  max_all = max_df[
    get_temp_columns(config)
  ].max()

  # 指定地点 & 指定日の最小値を取得
  min_location_daily_df = min_df[
    (min_df["location"] == location) &
    (min_df["月"] == target_month) &
    (min_df["日"] == target_day)
  ]
  # スコア計算用に加工
  min_loc_day = min_location_daily_df[
    get_temp_columns(config)
  ].iloc[0]

  # 指定地点 & 指定月の最小値を取得
  min_location_month_df = min_df[
    (min_df["location"] == location) &
    (min_df["月"] == target_month)
  ]
  # スコア計算用に加工
  min_loc_mon = min_location_month_df[
    get_temp_columns(config)
  ].min()

  # 指定地点 & 全期間の最小値を取得
  min_location_all_df = min_df[
    (min_df["location"] == location)
  ]
  # スコア計算用に加工
  min_loc_all = min_location_all_df[
    get_temp_columns(config)
  ].min()

  # 全地点 指定日の最小値を取得
  min_daily_df = min_df[
    (min_df["月"] == target_month) &
    (min_df["日"] == target_day)
  ]
  # スコア計算用に加工
  min_day = min_daily_df[
    get_temp_columns(config)
  ].min()

  # 全地点 & 指定月の最小値を取得
  min_month_df = min_df[
    (min_df["月"] == target_month)
  ]
  # スコア計算用に加工
  min_mon = min_month_df[
    get_temp_columns(config)
  ].min()

  # 全地点 & 全期間の最小値を取得、加工
  min_all = min_df[
    get_temp_columns(config)
  ].min()

  """
  print("指定地点・指定日")
  print(max_loc_day)
  print(min_loc_day)
  print("指定地点・指定月")
  print(max_loc_mon)
  print(min_loc_mon)
  print("指定地点・全期間")
  print(max_loc_all)
  print(min_loc_all)
  print("全地点・指定日")
  print(max_day)
  print(min_day)
  print("全地点・指定月")
  print(max_mon)
  print(min_mon)
  print("全地点・全期間")
  print(max_all)
  print(min_all)
  """

  # 基準値の整形
  base = target_temp[
    get_temp_columns(config)
  ].iloc[0]

  # スコアのラベル(カラム名)を設定
  label = get_score_calc_columns(config)

  # スコア計算
  result = pd.DataFrame({
    label["loc_day"]: calc_score(base, max_loc_day, min_loc_day),
    label["loc_mon"]: calc_score(base, max_loc_mon, min_loc_mon),
    label["loc_all"]: calc_score(base, max_loc_all, min_loc_all),
    label["all_day"]: calc_score(base, max_day, min_day),
    label["all_mon"]: calc_score(base, max_mon, min_mon),
    label["all_all"]: calc_score(base, max_all, min_all)
  }).round().astype(int)

  return result

# --------------------
# CSV出力
# --------------------

# CSV出力前にフォーマットを整える
def make_csv_result(result, comparison, location_code, score, config):
  # 地点マスタを取得
  location_dir = Path(config["PATH"]["location_dir"])
  location_file = (location_dir / "locations.csv")
  station_type = location_code[0]
  block_no = location_code[1:]

  try:
    df = pd.read_csv(
      location_file, dtype={"block_no": str},
      encoding=config["CSV"]["output_encoding"]
    )

  except FileNotFoundError as e:
    raise FileNotFoundError("CSVファイルがありません")

  # 地点名取得
  location_name = df.loc[
    (df["station_type"] == station_type) &
    (df["block_no"] == block_no),
    ["name", "prefecture_name"]
  ].iloc[0]

  # 出力用DataFrameに 比較対象, 地点, スコアを追加
  result = result.copy()
  result.insert(0, "比較対象", comparison)
  result.insert(1, "地点", location_name["name"])
  result.insert(2, "都府県", location_name["prefecture_name"])
  result = result.reset_index()
  result = result.rename(columns={"index": "項目"})
  result = result.join(
    score,
    on="項目"
  )
  # print(result)

  return result

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

  input_dir = Path(
    config["PATH"]["data_dir"]
  )

  stats_dir = Path(
    config["PATH"]["stats_input_dir"]
  )

  # Avg Stats
  month_stats_file = (stats_dir / "month_stats.csv")
  daily_stats_file = (stats_dir / "daily_stats.csv")
  all_stats_file = (stats_dir / "overall_stats.csv")

  # Max, Min Stats
  max_stats_file = (stats_dir / "max_stats.csv")
  min_stats_file = (stats_dir / "min_stats.csv")

  output_dir = Path(
    config["PATH"]["result_dir"]
  )

  # --------------------
  # CLI
  # --------------------

  parser = argparse.ArgumentParser(
    description="気温分析ツール"
  )

  parser.add_argument(
    "--location",
    required=True,
    help="地点名を漢字または英字で指定"
  )

  parser.add_argument(
    "--prefecture",
    required=True,
    help="都府県名を漢字または英字で指定"
  )

  parser.add_argument(
    "--date",
    required=True,
    help="分析対象日をyyyymmddで指定"
  )

  args = parser.parse_args()

  logging.info("========== START ==========")

  try:
    # --------------------
    # CSV読み込み
    # --------------------

    # args.location, args.prefectureのチェック
    location_code = validate_location(args.location, args.prefecture, config)

    # CSV読み込み
    df = load_csv_files(input_dir, location_code, config)
    logging.info("CSV読み込み完了")

    # dfの「年月日」をdatetimeに変換
    df = prepare_date(df)

    # args.dateのチェック (OKだったら対象日を取得)
    target_date = validate_date(df, args.date)
    logging.info("date=%s", target_date)

    # --------------------
    # 分析
    # --------------------

    # 対象日の実測値を取得
    target_temp = get_target_temp(df, target_date)
    # print(target_temp)

    # 日ごとの平均値比較結果を取得
    result_daily = daily_diff(daily_stats_file, args.location, target_temp, config)
    # print(result_daily)

    # 月ごとの平均値比較結果を取得
    result_month = month_diff(month_stats_file, args.location, target_temp, config)
    # print(result_month)

    # 全期間の平均値比較結果を取得
    result_overall = all_diff(all_stats_file, args.location, target_temp, config)
    # print(result_overall)

    # 指定地点 & 指定日 から計算したスコアを取得
    score = make_score_df(max_stats_file, min_stats_file, args.location, target_temp, config)
    # print(score)

    # スコアのラベル(カラム名)を設定
    label = get_score_calc_columns(config)

    # 日ごとのスコアをそれぞれ格納
    score_daily = extract_score(score, label, "daily", config)

    # 月ごとのスコアをそれぞれ格納
    score_month = extract_score(score, label, "month", config)

    # 全期間のスコアをそれぞれ格納
    score_overall = extract_score(score, label, "overall", config)

    # --------------------
    # 出力
    # --------------------

    # 「比較対象」カラムの値設定
    comparison_month = str(target_date.month) + "月で比較"  # 月
    comparison_daily = str(target_date.month) + "月" + str(target_date.day) + "日で比較"  # 日
    comparison_overall = "全期間で比較" # 全期間

    # CSV出力用にフォーマット整形
    output_result_daily = make_csv_result(
      result_daily, comparison_daily, location_code, score_daily, config
    )
    output_result_month = make_csv_result(
      result_month, comparison_month, location_code, score_month, config
    )
    output_result_overall = make_csv_result(
      result_overall, comparison_overall, location_code, score_overall, config
    )

    result = pd.concat([
      output_result_daily,
      output_result_month,
      output_result_overall
    ], ignore_index=True)
    # print(result)

    # 出力ファイル名設定
    filename = (f"{args.location}_{location_code}_{args.date}.csv")
    # 出力パス設定
    output_file = (output_dir / filename)

    # CSV生成
    save_csv(result, output_file, config)
    print(f"\n出力先: {output_file}")
    logging.info("出力完了: %s", output_file)

  except (FileNotFoundError, ValueError) as e:
    logging.error(str(e))
    print(f"エラー: {e}")
    sys.exit(1)

  finally:
    logging.info("==========  END  ==========")


if __name__ == "__main__":
  main()