# weather2

JMAの気象データを自動取得・蓄積・分析するプロジェクト。
weather の後継プロジェクト。


# スクリプト
make_locations.py - ダウンロードやデータ紐づけに使用する地点マスタを生成

download_jma.py - 気象庁のサイトから過去の統計CSVをダウンロード

make_stats.py - 過去の統計CSVから平均値、最大値、最小値を抽出

main.py - 統計とstatsから平均値との差分やスコアを計算してCSVに出力

card.py - main.pyで出力されたCSVをHTML+CSSで可読性を高める


## 参考

気象庁 アメダス地点情報履歴ファイル
https://www.data.jma.go.jp/stats/data/mdrr/chiten/meta/amdmaster.index4

気象庁 地域気象観測所一覧 > 都府県・振興局表示番号表
https://www.jma.go.jp/jma/kishou/know/amedas/ame_master.pdf
