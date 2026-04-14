---
name: aktools-a-share
description: Use mcporter with the configured aktools MCP server to fetch A股/港股/美股基础行情, A股涨停池, 强势股池, 龙虎榜, 板块资金流, 个股新闻, 财务指标, and recent trading-day information. Trigger when the user asks for stock codes, stock prices, trading-day info, A股 market emotion clues, 涨停池/强势股/龙虎榜/资金流, or wants stock/news data via the locally connected aktools MCP instead of generic web search.
---

Use the local `mcporter` CLI with the configured `aktools` server.

## Preconditions

- Assume `mcporter` is installed and `aktools` is already registered in the user's home mcporter config.
- Before first use in a session, prefer a cheap sanity check like:
  - `mcporter call aktools.get_current_time`
- If that fails, say the aktools MCP bridge is not available rather than pretending.

## Primary commands

Use `exec` to call `mcporter` directly. Preferred selectors:

- `aktools.get_current_time`
- `aktools.search`
- `aktools.stock_info`
- `aktools.stock_prices`
- `aktools.stock_news`
- `aktools.stock_indicators_a`
- `aktools.stock_zt_pool_em`
- `aktools.stock_zt_pool_strong_em`
- `aktools.stock_lhb_ggtj_sina`
- `aktools.stock_sector_fund_flow_rank`
- `aktools.stock_news_global`

## Common patterns

### 1) Get recent A股 trading-day info

```bash
mcporter call aktools.get_current_time
```

### 2) Search stock code

```bash
mcporter call aktools.search keyword=东方财富 market=sz
```

If the user gives a company name without code, search first.

### 3) Get stock history

A股 examples:

```bash
mcporter call aktools.stock_prices symbol=600519 market=sh period=daily limit=20
mcporter call aktools.stock_prices symbol=000001 market=sz period=daily limit=30
```

### 4) Get A股 finance indicators

```bash
mcporter call aktools.stock_indicators_a symbol=600519
```

### 5) Get market emotion clues

Use these for 盘前/复盘/情绪判断:

```bash
mcporter call aktools.stock_zt_pool_em
mcporter call aktools.stock_zt_pool_strong_em
mcporter call aktools.stock_lhb_ggtj_sina days=5 limit=30
mcporter call aktools.stock_sector_fund_flow_rank days=今日 cate=概念资金流
mcporter call aktools.stock_news_global
```

## Market/code rules

- For A股, use:
  - `sh` for Shanghai codes like `600519`
  - `sz` for Shenzhen codes like `000001`, `300750`
- If the user only gives a plain 6-digit code:
  - codes starting with `6` usually map to `sh`
  - codes starting with `0` or `3` usually map to `sz`
- If uncertain, search first instead of guessing.

## Response style

- Do not dump raw CSV unless the user asks for raw output.
- Summarize the key takeaways in Chinese.
- For price/history queries, highlight:
  - latest close
  - recent trend
  - notable strength/weakness
- For market-emotion queries, synthesize from:
  - trading-day info
  - 涨停池 / 强势股池
  - 龙虎榜
  - 资金流
  - news

## Failure handling

- If `mcporter` or `aktools` call fails, say the local aktools MCP bridge is unavailable and include the failing selector when helpful.
- If one market-data call fails, try one adjacent data source/tool before giving up.
- Do not fabricate stock data.
