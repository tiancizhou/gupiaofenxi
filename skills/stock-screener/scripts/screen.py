#!/usr/bin/env python3
"""
A股选股脚本：近N日跌幅区间 + 近M日涨幅上限 + 最新季报盈利

依赖：
  - 新浪财经接口（全市场行情，无需安装额外包）
  - mcporter + aktools MCP（K线、财务指标）

用法示例：
  python3 screen.py
  python3 screen.py --days 5 --low 15 --high 30 --month-days 22 --month-max 30
  python3 screen.py --no-profit-filter
"""
import argparse
import subprocess
import urllib.request
import json
import csv
import io
import time


def parse_args():
    p = argparse.ArgumentParser(description='A股选股器')
    p.add_argument('--days', type=int, default=5, help='近N个交易日跌幅（默认5）')
    p.add_argument('--low', type=float, default=15, help='跌幅下限，默认15')
    p.add_argument('--high', type=float, default=30, help='跌幅上限，默认30')
    p.add_argument('--month-days', type=int, default=22, help='近M个交易日涨幅上限窗口，默认22')
    p.add_argument('--month-max', type=float, default=30, help='近M日涨幅上限，默认30')
    p.add_argument('--no-profit-filter', action='store_true', help='跳过财务盈利过滤')
    p.add_argument('--today-drop', type=float, default=3.0,
                   help='今日跌幅预筛阈值，只查今日跌幅超过此值的股票（默认3%%）')
    return p.parse_args()


def fetch_market_stocks(today_drop_threshold=3.0):
    """从新浪财经拉全市场行情，返回今日跌幅超过阈值的股票列表"""
    all_stocks = []
    for page in range(1, 80):
        url = (f'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php'
               f'/Market_Center.getHQNodeData?page={page}&num=80'
               f'&sort=changepercent&asc=1&node=hs_a&_s_r_a=page')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', 'Referer': 'https://finance.sina.com.cn'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8', errors='ignore'))
            if not data:
                break
            for item in data:
                try:
                    cp = float(item.get('changepercent', 0))
                except (ValueError, TypeError):
                    cp = 0
                if cp > -today_drop_threshold:
                    # 升序排列，后面的跌幅更小，直接停
                    all_stocks.append({'code': item['code'],
                                       'name': item['name'],
                                       'changepercent': cp,
                                       'market': 'sh' if item['symbol'].startswith('sh') else 'sz'})
                    continue
                all_stocks.append({'code': item['code'],
                                   'name': item['name'],
                                   'changepercent': cp,
                                   'market': 'sh' if item['symbol'].startswith('sh') else 'sz'})
            time.sleep(0.12)
        except Exception as e:
            print(f'  新浪接口 page {page} 错误: {e}')
            break

    # 只保留今日跌幅超过阈值的候选
    candidates = [s for s in all_stocks if s['changepercent'] <= -today_drop_threshold]
    return candidates


def get_kline(code, market, limit=35):
    """用 aktools 拉日K线，返回行列表（时间升序），失败返回 None"""
    cmd = [
        'mcporter', 'call', 'aktools.stock_prices',
        '--args', json.dumps({'symbol': code, 'market': market, 'period': 'daily', 'limit': limit})
    ]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=20)
        lines = [l for l in out.strip().splitlines() if l.strip()]
        if len(lines) < 3:
            return None
        reader = csv.DictReader(io.StringIO('\n'.join(lines)))
        return list(reader)
    except Exception:
        return None


def calc_pct(rows, n):
    """计算最近 n 个交易日的累计涨跌幅，rows 为时间升序列表"""
    if len(rows) < n + 1:
        return None
    try:
        close_now = float(rows[-1]['收盘'])
        close_n_ago = float(rows[-(n + 1)]['收盘'])
        return (close_now - close_n_ago) / close_n_ago * 100
    except (ValueError, KeyError):
        return None


def get_net_profit(code):
    """用 aktools 查A股财务指标，返回 (报告期, 净利润str, 是否为正)"""
    cmd = ['mcporter', 'call', 'aktools.stock_indicators_a',
           '--args', json.dumps({'symbol': code})]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=20)
        lines = [l for l in out.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            return None, None, False
        reader = csv.DictReader(io.StringIO('\n'.join(lines)))
        rows = list(reader)
        last = rows[-1]
        report = last.get('报告期', '')
        net_profit = last.get('净利润', '').strip()
        is_positive = bool(net_profit) and not net_profit.startswith('-')
        return report, net_profit, is_positive
    except Exception:
        return None, None, False


def main():
    args = parse_args()

    print(f'[1/4] 拉取全市场行情（今日跌幅 > {args.today_drop}% 的候选）...')
    candidates = fetch_market_stocks(args.today_drop)
    print(f'      候选: {len(candidates)} 只')

    if not candidates:
        print('没有候选股票，退出。')
        return

    nd_label = f'{args.days}日%'
    md_label = f'{args.month_days}日%'

    print(f'[2/4] 查K线，筛选近{args.days}日跌幅 -{args.low}%~-{args.high}%，'
          f'近{args.month_days}日涨幅 <= {args.month_max}%...')
    kline_passed = []
    for i, c in enumerate(candidates):
        if i % 50 == 0:
            print(f'      进度: {i}/{len(candidates)}')
        rows = get_kline(c['code'], c['market'], limit=args.month_days + 13)
        if rows is None:
            continue
        pct_nd = calc_pct(rows, args.days)
        pct_md = calc_pct(rows, args.month_days)
        if pct_nd is None or pct_md is None:
            continue
        if -args.high <= pct_nd <= -args.low and pct_md <= args.month_max:
            c['pct_nd'] = round(pct_nd, 2)
            c['pct_md'] = round(pct_md, 2)
            kline_passed.append(c)
        time.sleep(0.1)
    print(f'      K线筛选后: {len(kline_passed)} 只')

    if args.no_profit_filter:
        final = kline_passed
        for c in final:
            c['report'] = 'N/A'
            c['net_profit'] = 'N/A'
    else:
        print('[3/4] 查财务指标，过滤亏损股...')
        final = []
        for c in kline_passed:
            report, net_profit, is_positive = get_net_profit(c['code'])
            if is_positive:
                c['report'] = report
                c['net_profit'] = net_profit
                final.append(c)
            time.sleep(0.1)

    print(f'\n=== 最终结果: {len(final)} 只 ===')
    print(f'{"代码":<8} {"名称":<10} {"今日%":<8} {nd_label:<10} {md_label:<10} {"净利润":<12} 报告期')
    print('-' * 72)
    for c in sorted(final, key=lambda x: x['pct_nd']):
        print(f"{c['code']:<8} {c['name']:<10} {c['changepercent']:<8.2f} "
              f"{c['pct_nd']:<10.2f} {c['pct_md']:<10.2f} "
              f"{c.get('net_profit', ''):<12} {c.get('report', '')}")


if __name__ == '__main__':
    main()
