import requests
import json

url = "https://www.data.jma.go.jp/risk/obsdl/show/table"

data = {
    "stationNumList": json.dumps(["a1018"]),
    "aggrgPeriod": "1",
    "elementNumList": json.dumps([
      ["101",""],   # 合計降水量
      ["201",""],   # 平均気温
      ["202",""],   # 最高気温
      ["203",""],   # 最低気温
      ["301",""],   # 平均湿度
      ["401",""],   # 平均風速
      ["501",""],   # 日照時間
      ["605",""]    # 合計積雪量
    ]),
    "interAnnualType": "2",
    "ymdList": json.dumps([
      "1995", "2004", "1", "12", "1", "31"
    ]),
    "optionNumList": "[]",
    "downloadFlag": "true",
    "rmkFlag": "1",
    "disconnectFlag": "1",
    "youbiFlag": "0",
    "fukenFlag": "0",
    "kijiFlag": "0",
    "csvFlag": "1",
    "jikantaiFlag": "0",
    "jikantaiList": "[]",
    "ymdLiteral": "1",
}

response = requests.post(url, data=data)

response.raise_for_status()

with open("data.csv", "wb") as f:
  f.write(response.content)