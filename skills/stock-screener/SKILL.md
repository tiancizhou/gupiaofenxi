---
name: stock-screener
description: A股选股 skill：筛选近N日累计跌幅在指定区间内、近M日涨幅不超过阈值、且最新季报盈利的股票。使用新浪财经接口拉取全市场行情（支持网络环境），用 aktools MCP 查历史K线和财务指标。触发词：选股、筛股、跌幅选股、回调股票、业绩正的跌幅股。
---

# Stock Screener — A股回调选股

## 功能概述

筛选满足以下全部条件的 A 股：
1. 近 N 个交易日（默认5日）累计跌幅在 [low%, high%]（默认 -30% ~ -15%）
2. 近 M 个交易日（默认22日，约1个月）涨跌幅不超过上限（默认 +30%）
3. 最新一期季报净利润为正（盈利）

## 数据源

- **全市场行情**：新浪财经 `vip.stock.finance.sina.com.cn`（无需代理，国内直连）
- **历史K线 / 财务指标**：aktools MCP（`mcporter call aktools.stock_prices` / `aktools.stock_indicators_a`）

## 执行流程

### Step 1：拉全市场行情，初筛今日跌幅候选

今日跌幅 ≤ -3% 的股票最可能在5日内累计跌超15%，用它缩小候选池。

```bash
python3 scripts/fetch_candidates.py [--today-drop -3] [--max-pages 80]
```

输出：候选股票列表（code, market, name, today_pct）写入 `/tmp/screener_candidates.json`

### Step 2：计算近5日累计跌幅，筛选目标区间

对候选股票逐一调用 aktools 查历史K线，计算 N 日累计涨跌幅。

```bash
python3 scripts/calc_nd_change.py [--days 5] [--low -30] [--high -15]
```

输出：符合5日跌幅条件的股票写入 `/tmp/screener_5d.json`

### Step 3：计算近22日涨跌幅，过滤近期涨幅过大的股票

同一批 K 线数据（limit=35 已包含22日），直接计算。

### Step 4：查财务指标，过滤亏损股

```bash
python3 scripts/filter_profitable.py
```

调用 `aktools.stock_indicators_a`，取最新一期净利润，过滤负值。

### Step 5：汇总输出

按5日跌幅从大到小排列，输出：代码、名称、5日涨跌、近1月涨跌、最新净利润、报告期。

## 一键脚本

以上4步合并在一个脚本中：

```bash
python3 scripts/screen.py
```

默认参数：5日跌幅 -30%~-15%，近22日涨幅上限 +30%，今日跌幅预筛阈值 -3%。

## 关键实现细节

### 新浪行情接口

```
GET https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData
  ?page=<N>&num=80&sort=changepercent&asc=1&node=hs_a&_s_r_a=page
```

- 按涨跌幅升序（跌幅最大在前）分页拉取
- `changepercent` 字段为字符串，需 `float()` 转换
- 今日涨跌幅字段：`changepercent`；现价：`trade`
- 市场判断：code 首位 `6` → sh，`0`/`3` → sz

### aktools K线接口

```bash
mcporter call aktools.stock_prices --args '{"symbol":"600691","market":"sh","period":"daily","limit":35}'
```

- 返回 CSV 格式，含字段：日期,开盘,收盘,最高,最低...
- limit=35 足够覆盖22个交易日（含节假日buffer）
- 5日涨跌 = (rows[-1]['收盘'] - rows[-6]['收盘']) / rows[-6]['收盘'] * 100
- 22日涨跌 = (rows[-1]['收盘'] - rows[-23]['收盘']) / rows[-23]['收盘'] * 100

### aktools 财务指标接口

```bash
mcporter call aktools.stock_indicators_a --args '{"symbol":"600691"}'
```

- 返回 CSV，字段含：报告期,净利润,...
- 取最后一行（最新期），判断净利润是否以 `-` 开头

### 市场代码推断

```python
def infer_market(code):
    if code.startswith('6'):
        return 'sh'
    return 'sz'
```

## 注意事项

- 东方财富接口（akshare `stock_zh_a_spot_em`）在部分网络环境不通，优先用新浪接口
- aktools `stock_prices` 的 `symbol` 参数必须为字符串，用 `--args` JSON 传参（`key=value` 方式会被解析为 int）
- 新浪接口偶发 502，单页失败时跳过继续
- 非交易日运行时数据为上一交易日收盘价，结果仍有效
