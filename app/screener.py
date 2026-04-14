from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

import akshare as ak


def infer_market(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    return "sz"


def fetch_candidates(today_drop_threshold: float = 3.0) -> list[dict[str, Any]]:
    all_stocks: list[dict[str, Any]] = []
    for page in range(1, 80):
        url = (
            f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
            f"/Market_Center.getHQNodeData?page={page}&num=80"
            f"&sort=changepercent&asc=1&node=hs_a&_s_r_a=page"
        )
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://finance.sina.com.cn",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if not data:
                break
            for item in data:
                try:
                    cp = float(item.get("changepercent", 0))
                except (ValueError, TypeError):
                    cp = 0
                if cp > -today_drop_threshold:
                    continue
                all_stocks.append(
                    {
                        "code": item["code"],
                        "name": item["name"],
                        "changepercent": cp,
                        "market": "sh" if item["symbol"].startswith("sh") else "sz",
                    }
                )
            time.sleep(0.12)
        except Exception:
            break
    return all_stocks


def get_kline(code: str, market: str, limit: int = 35) -> list[dict[str, Any]] | None:
    try:
        frame = ak.stock_zh_a_hist(
            symbol=code, period="daily", start_date="", end_date="", adjust=""
        )
        rows = frame.to_dict(orient="records")
        if len(rows) < 3:
            return None
        return rows[-limit:]
    except Exception:
        return None


def calc_pct(rows: list[dict[str, Any]], n: int) -> float | None:
    if len(rows) < n + 1:
        return None
    try:
        close_key = None
        for key in rows[0]:
            if key in ("收盘", "close", "收盘价"):
                close_key = key
                break
        if close_key is None:
            return None
        close_now = float(rows[-1][close_key])
        close_n_ago = float(rows[-(n + 1)][close_key])
        return (close_now - close_n_ago) / close_n_ago * 100
    except (ValueError, KeyError, TypeError):
        return None


def get_net_profit(code: str) -> tuple[str | None, str | None, bool]:
    try:
        frame = ak.stock_financial_abstract_ths(symbol=code)
        rows = frame.to_dict(orient="records")
        if not rows:
            return None, None, False
        last = rows[-1]
        report = str(last.get("报告期", "")).strip()
        net_profit = str(last.get("净利润", "")).strip()
        is_positive = bool(net_profit) and not net_profit.startswith("-")
        return report, net_profit, is_positive
    except Exception:
        return None, None, False


def screen(
    days: int = 5,
    low: float = 15,
    high: float = 30,
    month_days: int = 22,
    month_max: float = 30,
    today_drop: float = 3.0,
    profit_filter: bool = True,
) -> list[dict[str, Any]]:
    candidates = fetch_candidates(today_drop)
    if not candidates:
        return []

    kline_passed: list[dict[str, Any]] = []
    for c in candidates:
        rows = get_kline(c["code"], c["market"], limit=month_days + 13)
        if rows is None:
            continue
        pct_nd = calc_pct(rows, days)
        pct_md = calc_pct(rows, month_days)
        if pct_nd is None or pct_md is None:
            continue
        if -high <= pct_nd <= -low and pct_md <= month_max:
            c["pct_nd"] = round(pct_nd, 2)
            c["pct_md"] = round(pct_md, 2)
            kline_passed.append(c)
        time.sleep(0.1)

    if not profit_filter:
        for c in kline_passed:
            c["report"] = "N/A"
            c["net_profit"] = "N/A"
        return sorted(kline_passed, key=lambda x: x["pct_nd"])

    final: list[dict[str, Any]] = []
    for c in kline_passed:
        report, net_profit, is_positive = get_net_profit(c["code"])
        if is_positive:
            c["report"] = report
            c["net_profit"] = net_profit
            final.append(c)
        time.sleep(0.1)

    return sorted(final, key=lambda x: x["pct_nd"])
