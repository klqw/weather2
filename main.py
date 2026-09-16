import argparse
import configparser
import logging
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import psycopg
from psycopg.rows import dict_row
from db import get_connection

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

def get_weather_observations(location_data, config):
  sql = """
      SELECT
        location_id,
        observed_date,
        avg_temp,
        max_temp,
        min_temp,
        avg_humidity,
        sunshine_hours,
        precipitation,
        avg_wind_speed,
        max_snow_depth
      FROM weather_observations
      WHERE location_id = %s;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
          sql,
          (location_data["location_id"], )
        )
        weather_observations_data = cur.fetchall()

        if weather_observations_data is None:
          raise ValueError(f"指定された地点のデータが取得できませんでした location_id: {location_data["location_id"]}")

        return weather_observations_data

  except psycopg.Error as e:
    raise RuntimeError("weather_observationsテーブルからの取得に失敗しました") from e


def get_location(location, prefecture, config):
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
  

# --------------------
# argバリデーション
# --------------------

# location, prefecture
def validate_location(location, prefecture, config):
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
          raise ValueError(f"地点名と都府県名の組み合わせが不正です 地点名: {location}, 都府県名: {prefecture}")

        # 取得対象が1件だった場合は取得対象地点のlocation情報を返す
        logging.info("取得対象 地点名: %s, 都府県名: %s", location, prefecture)

        return location_data

  except psycopg.Error as e:
    raise RuntimeError("locationテーブルからの取得に失敗しました") from e

# date
def validate_date(df, date):
  try:
    target_date = pd.to_datetime(
      date,
      format="%Y%m%d"
    )
  except ValueError:
    raise ValueError(f"不正なdateです: {date}")

  if not df["observed_date"].eq(target_date).any():
    raise ValueError(
      f"指定されたdateのデータがありません: {date}"
    )

  return target_date

# --------------------
# データいじり
# --------------------

# 1件以上取得確認
def get_stats(cur, sql, stats_name):
  cur.execute(sql)
  rows = cur.fetchall()

  if not rows:
    raise ValueError(f"{stats_name}の取得結果が0件です")

  return rows

# daily_avg_stats取得
def get_daily_avg_stats(config, stats_name):
  sql = """
    SELECT
      location_id,
      month,
      day,
      avg_temp,
      max_temp,
      min_temp,
      avg_humidity,
      sunshine_hours,
      precipitation,
      avg_wind_speed,
      max_snow_depth
    FROM daily_avg_stats;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name)

  except psycopg.Error as e:
    raise RuntimeError(f"{stats_name}テーブルからの取得に失敗しました") from e

# month_avg_stats取得
def get_month_avg_stats(config, stats_name):
  sql = """
    SELECT
      location_id,
      month,
      avg_temp,
      max_temp,
      min_temp,
      avg_humidity,
      sunshine_hours,
      precipitation,
      avg_wind_speed,
      max_snow_depth
    FROM month_avg_stats;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name)

  except psycopg.Error as e:
    raise RuntimeError(f"{stats_name}テーブルからの取得に失敗しました") from e

# overall_avg_stats取得
def get_overall_avg_stats(config, stats_name):
  sql = """
    SELECT
      location_id,
      avg_temp,
      max_temp,
      min_temp,
      avg_humidity,
      sunshine_hours,
      precipitation,
      avg_wind_speed,
      max_snow_depth
    FROM overall_avg_stats;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name)

  except psycopg.Error as e:
    raise RuntimeError(f"{stats_name}テーブルからの取得に失敗しました") from e

# daily_max_stats取得
def get_daily_max_stats(config, stats_name):
  sql = """
    SELECT
      location_id,
      month,
      day,
      avg_temp,
      max_temp,
      min_temp,
      avg_humidity,
      sunshine_hours,
      precipitation,
      avg_wind_speed,
      max_snow_depth
    FROM daily_max_stats;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name)

  except psycopg.Error as e:
    raise RuntimeError(f"{stats_name}テーブルからの取得に失敗しました") from e

# daily_min_stats取得
def get_daily_min_stats(config, stats_name):
  sql = """
    SELECT
      location_id,
      month,
      day,
      avg_temp,
      max_temp,
      min_temp,
      avg_humidity,
      sunshine_hours,
      precipitation,
      avg_wind_speed,
      max_snow_depth
    FROM daily_min_stats;
  """

  try:
    with get_connection(config) as conn:
      with conn.cursor(row_factory=dict_row) as cur:
        return get_stats(cur, sql, stats_name)

  except psycopg.Error as e:
    raise RuntimeError(f"{stats_name}テーブルからの取得に失敗しました") from e


# 表示項目の設定
def get_temp_columns():
  return [
    "avg_temp",        # 平均気温(℃)
    "max_temp",        # 最高気温(℃)
    "min_temp",        # 最低気温(℃)
    "avg_humidity",    # 平均湿度(％)
    "sunshine_hours",  # 日照時間(時間)
    "avg_wind_speed",  # 平均風速(m/s)
    "precipitation",   # 降水量の合計(mm)
    "max_snow_depth"   # 最深積雪(cm)
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

    elif max_value[column] == min_value[column]:
      result[column] = 0

    else:
      result[column] = (base_value[column] - min_value[column]) / (max_value[column] - min_value[column]) * 99 + 1

  return result

# スコア計算時のラベル(カラム名)を設定
def get_score_calc_columns(config):
  return {
    "loc_day": config["SCORE_LABEL"]["location_daily_score"],
    "loc_mon": config["SCORE_LABEL"]["location_month_score"],
    "loc_all": config["SCORE_LABEL"]["location_overall_score"],
    "all_day": config["SCORE_LABEL"]["all_daily_score"],
    "all_mon": config["SCORE_LABEL"]["all_month_score"],
    "all_all": config["SCORE_LABEL"]["all_overall_score"]
  }

# スコア出力時のラベル(カラム名)を設定
def get_score_out_columns(config):
  return [
    config["SCORE_LABEL"]["output_location_score"],
    config["SCORE_LABEL"]["output_all_score"]
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


# 指定日の実測値を取得
def get_target_temp(df, target_date):
  return df[
    df["observed_date"] == target_date
  ]

# --------------------
# 指定日付の差分分析
# --------------------

# 指定日と日ごとの比較
def daily_diff(df, target_data):

  # ターゲット地点のlocation_idを取得
  location_id = target_data["location_id"].iloc[0]

  # 指定日の月・日を取得
  target_month = target_data["month"].iloc[0]
  target_day = target_data["day"].iloc[0]

  # 指定日の月・日に対する平均値を取得
  df = df[
    (df["month"] == target_month) &
    (df["day"] == target_day)
  ]

  # 全地点の指定日の月・日に対する平均値を取得
  all_avg = df.groupby(["location_id", "month", "day"])[
    get_temp_columns()
  ].mean()
  all_avg = all_avg.mean().to_frame().T
  # print(all_avg)

  # ターゲット地点の指定日の月・日に対する平均値を取得
  target_avg = df[
    df["location_id"] == location_id
  ]
  # print(target_avg)

  # target_tempを比較用に加工
  actual = target_data[
    get_temp_columns()
  ].iloc[0]

  # 全地点の指定日の月・日に対する平均値を比較用に加工
  base_all = all_avg[
    get_temp_columns()
  ].iloc[0]

  # ターゲット地点の指定日の月・日に対する平均値を比較ように加工
  base_target = target_avg[
    get_temp_columns()
  ].iloc[0]

  return pd.DataFrame({
    "実測値": actual,
    "地点基準値": base_target,
    "差(地点)": calc_diff(actual, base_target),
    "全体基準値": base_all,
    "差(全体)": calc_diff(actual, base_all)
  }).round(1)

# 指定日と月ごとの比較
def month_diff(df, target_data):

  # ターゲット地点のlocation_idを取得
  location_id = target_data["location_id"].iloc[0]

  # 指定日の月を取得
  target_month = target_data["month"].iloc[0]

  # 指定日の月に対応する平均値を取得
  df = df[
    df["month"] == target_month
  ]

  # 全地点の指定日の月に対する平均値を取得
  all_avg = df.groupby(["location_id", "month"])[
    get_temp_columns()
  ].mean()
  all_avg = all_avg.mean().to_frame().T
  # print(all_avg)

  # ターゲット地点の指定日の月に対する平均値を取得
  target_avg = df[
    df["location_id"] == location_id
  ]
  # print(target_avg)

  # target_dataを比較用に加工
  actual = target_data[
    get_temp_columns()
  ].iloc[0]

  # 全地点の指定日の月に対する平均値を比較用に加工
  base_all = all_avg[
    get_temp_columns()
  ].iloc[0]

  # ターゲット地点の指定日の月に対する平均値を比較用に加工
  base_target = target_avg[
    get_temp_columns()
  ].iloc[0]

  return pd.DataFrame({
    "実測値": actual,
    "地点基準値": base_target,
    "差(地点)": calc_diff(actual, base_target),
    "全体基準値": base_all,
    "差(全体)": calc_diff(actual, base_all)
  }).round(1)

# 指定日と全期間の比較
def all_diff(df, target_data):

  # ターゲット地点のlocation_idを取得
  location_id = target_data["location_id"].iloc[0]

  # 全地点の平均値を取得
  all_avg = df.mean(numeric_only=True).to_frame().T
  # print(all_avg)

  # ターゲット地点の平均値を取得
  target_avg = df[
    df["location_id"] == location_id
  ]
  # print(target_avg)

  # target_tempを比較用に加工
  actual = target_data[
    get_temp_columns()
  ].iloc[0]

  # 全地点の平均値を比較用に加工
  base_all = all_avg[
    get_temp_columns()
  ].iloc[0]

  # ターゲット地点の平均値を比較用に加工
  base_target = target_avg[
    get_temp_columns()
  ].iloc[0]

  return pd.DataFrame({
    "実測値": actual,
    "地点基準値": base_target,
    "差(地点)": calc_diff(actual ,base_target),
    "全体基準値": base_all,
    "差(全体)": calc_diff(actual, base_all)
  }).round(1)
  
# 指定日の最大値と最小値からスコア計算したdfを出力
def make_score(max_df, min_df, target_data, config):

  # ターゲット地点のlocation_idを取得
  location_id = target_data["location_id"].iloc[0]

  # 指定日の月・日を取得
  target_month = target_data["month"].iloc[0]
  target_day = target_data["day"].iloc[0]

  # 指定地点 & 指定日の最大値を取得
  max_location_daily_df = max_df[
    (max_df["location_id"] == location_id) &
    (max_df["month"] == target_month) &
    (max_df["day"] == target_day)
  ]
  # スコア計算用に加工
  max_loc_day = max_location_daily_df[
    get_temp_columns()
  ].iloc[0]

  # 指定地点 & 指定月の最大値を取得
  max_location_month_df = max_df[
    (max_df["location_id"] == location_id) &
    (max_df["month"] == target_month)
  ]
  # スコア計算用に加工
  max_loc_mon = max_location_month_df[
    get_temp_columns()
  ].max()

  # 指定地点 & 全期間の最大値を取得
  max_location_all_df = max_df[
    (max_df["location_id"] == location_id)
  ]
  # スコア計算用に加工
  max_loc_all = max_location_all_df[
    get_temp_columns()
  ].max()

  # 全地点 指定日の最大値を取得
  max_daily_df = max_df[
    (max_df["month"] == target_month) &
    (max_df["day"] == target_day)
  ]
  # スコア計算用に加工
  max_day = max_daily_df[
    get_temp_columns()
  ].max()

  # 全地点 & 指定月の最大値を取得
  max_month_df = max_df[
    (max_df["month"] == target_month)
  ]
  # スコア計算用に加工
  max_mon = max_month_df[
    get_temp_columns()
  ].max()

  # 全地点 & 全期間の最大値を取得、加工
  max_all = max_df[
    get_temp_columns()
  ].max()

  # 指定地点 & 指定日の最小値を取得
  min_location_daily_df = min_df[
    (min_df["location_id"] == location_id) &
    (min_df["month"] == target_month) &
    (min_df["day"] == target_day)
  ]
  # スコア計算用に加工
  min_loc_day = min_location_daily_df[
    get_temp_columns()
  ].iloc[0]

  # 指定地点 & 指定月の最小値を取得
  min_location_month_df = min_df[
    (min_df["location_id"] == location_id) &
    (min_df["month"] == target_month)
  ]
  # スコア計算用に加工
  min_loc_mon = min_location_month_df[
    get_temp_columns()
  ].min()

  # 指定地点 & 全期間の最小値を取得
  min_location_all_df = min_df[
    (min_df["location_id"] == location_id)
  ]
  # スコア計算用に加工
  min_loc_all = min_location_all_df[
    get_temp_columns()
  ].min()

  # 全地点 指定日の最小値を取得
  min_daily_df = min_df[
    (min_df["month"] == target_month) &
    (min_df["day"] == target_day)
  ]
  # スコア計算用に加工
  min_day = min_daily_df[
    get_temp_columns()
  ].min()

  # 全地点 & 指定月の最小値を取得
  min_month_df = min_df[
    (min_df["month"] == target_month)
  ]
  # スコア計算用に加工
  min_mon = min_month_df[
    get_temp_columns()
  ].min()

  # 全地点 & 全期間の最小値を取得、加工
  min_all = min_df[
    get_temp_columns()
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
  base = target_data[
    get_temp_columns()
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
def make_csv_result(result, comparison, location_data, score):

  # 出力用DataFrameに 比較対象, 地点, スコアを追加
  result = result.copy()
  result.insert(0, "比較対象", comparison)
  result.insert(1, "地点", location_data["name"])
  result.insert(2, "都府県", location_data["prefecture_name"])
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

  # 5つの集計取得を共通タスク化
  stats_tasks = [
    ("daily_avg_stats", get_daily_avg_stats),
    ("month_avg_stats", get_month_avg_stats),
    ("overall_avg_stats", get_overall_avg_stats),
    ("daily_max_stats", get_daily_max_stats),
    ("daily_min_stats", get_daily_min_stats)
  ]

  # index(column)名を和名へ変換するための準備
  column_map = dict(config["COLUMN"])

  # 出力先ディレクトリパス設定
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
    # DB読み込み
    # --------------------

    # args.location, args.prefectureのチェック
    location_data = validate_location(args.location, args.prefecture, config)

    # location_code
    location_code = location_data["station_type"] + location_data["block_no"]

    # weather_observations読み込み
    get_weather_observations_data = get_weather_observations(location_data, config)
    logging.info("DB取得完了")
    df = pd.DataFrame(get_weather_observations_data)

    # 日付型へ変換
    df["observed_date"] = pd.to_datetime(df["observed_date"])

    # 月・日を追加
    df["month"] = df["observed_date"].dt.month
    df["day"] = df["observed_date"].dt.day


    # --------------------
    # 集計結果取得
    # --------------------
    stats_data = {}
    for name, getter in stats_tasks:
      stats_data[name] = pd.DataFrame(getter(config, name))

    # args.dateのチェック (OKだったら対象日を取得)
    target_date = validate_date(df, args.date)
    logging.info("date=%s", target_date)

    # --------------------
    # 分析
    # --------------------

    # 対象日の実測値を取得
    target_data = get_target_temp(df, target_date)
    target_data.rename(index=column_map, inplace=True)
    # print(target_data)

    # 日ごとの平均値比較結果を取得
    result_daily = daily_diff(stats_data["daily_avg_stats"], target_data)
    result_daily.rename(index=column_map, inplace=True)
    # print(result_daily)

    # 月ごとの平均値比較結果を取得
    result_month = month_diff(stats_data["month_avg_stats"], target_data)
    result_month.rename(index=column_map, inplace=True)
    # print(result_month)

    # 全期間の平均値比較結果を取得
    result_overall = all_diff(stats_data["overall_avg_stats"], target_data)
    result_overall.rename(index=column_map, inplace=True)
    # print(result_overall)

    # 指定地点 & 指定日 から計算したスコアを取得
    score = make_score(
              stats_data["daily_max_stats"],
              stats_data["daily_min_stats"],
              target_data,
              config
            )
    score.rename(index=column_map, inplace=True)
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
      result_daily, comparison_daily, location_data, score_daily
    )
    output_result_month = make_csv_result(
      result_month, comparison_month, location_data, score_month
    )
    output_result_overall = make_csv_result(
      result_overall, comparison_overall, location_data, score_overall
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