from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import akshare as ak


def infer_market(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    return "sz"


def _tool_schema(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def get_tool_definitions() -> list[dict[str, Any]]:
    return [
        _tool_schema(
            "get_stock_price",
            "Get recent A-share price history for a stock code.",
            {
                "symbol": {
                    "type": "string",
                    "description": "A-share stock code, e.g. 600519",
                },
                "limit": {
                    "type": "integer",
                    "description": "Recent row count",
                    "default": 20,
                },
            },
            ["symbol"],
        ),
        _tool_schema(
            "get_stock_info",
            "Get basic company information for a stock code.",
            {"symbol": {"type": "string", "description": "A-share stock code"}},
            ["symbol"],
        ),
        _tool_schema(
            "get_financial_indicators",
            "Get financial summary indicators for a stock code.",
            {"symbol": {"type": "string", "description": "A-share stock code"}},
            ["symbol"],
        ),
        _tool_schema(
            "get_stock_news",
            "Get recent stock news for a stock code.",
            {"symbol": {"type": "string", "description": "A-share stock code"}},
            ["symbol"],
        ),
        _tool_schema(
            "get_market_sentiment",
            "Get A-share market sentiment signals like limit-up pool and fund flow.",
            {},
            [],
        ),
        _tool_schema(
            "get_global_news",
            "Get recent macro or global finance news.",
            {},
            [],
        ),
        _tool_schema(
            "screen_stocks",
            "Screen A-share stocks by recent pullback, monthly change, and profitability.",
            {
                "days": {"type": "integer", "default": 5},
                "low": {"type": "number", "default": 15},
                "high": {"type": "number", "default": 30},
                "month_days": {"type": "integer", "default": 22},
                "month_max": {"type": "number", "default": 30},
            },
            [],
        ),
    ]


def _frame_to_records(frame: Any, limit: int | None = None) -> list[dict[str, Any]]:
    records = frame.to_dict(orient="records")
    if limit is not None:
        return records[:limit]
    return records


def get_stock_price(symbol: str, limit: int = 20) -> dict[str, Any]:
    frame = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="")
    return {
        "ok": True,
        "symbol": symbol,
        "market": infer_market(symbol),
        "rows": _frame_to_records(frame, limit),
    }


def get_stock_info(symbol: str) -> dict[str, Any]:
    frame = ak.stock_individual_info_em(symbol=symbol)
    return {"ok": True, "symbol": symbol, "info": _frame_to_records(frame)}


def get_financial_indicators(symbol: str) -> dict[str, Any]:
    frame = ak.stock_financial_abstract_ths(symbol=symbol)
    return {"ok": True, "symbol": symbol, "items": _frame_to_records(frame, 20)}


def get_stock_news(symbol: str) -> dict[str, Any]:
    frame = ak.stock_news_em(symbol=symbol)
    return {"ok": True, "symbol": symbol, "news": _frame_to_records(frame, 20)}


def get_market_sentiment() -> dict[str, Any]:
    zt_pool = ak.stock_zt_pool_em()
    fund_flow = ak.stock_sector_fund_flow_rank(
        indicator="今日", sector_type="概念资金流"
    )
    return {
        "ok": True,
        "limit_up_pool": _frame_to_records(zt_pool, 20),
        "sector_fund_flow": _frame_to_records(fund_flow, 20),
    }


def get_global_news() -> dict[str, Any]:
    frame = ak.news_cctv(date="")
    return {"ok": True, "news": _frame_to_records(frame, 20)}


def screen_stocks(
    days: int = 5,
    low: float = 15,
    high: float = 30,
    month_days: int = 22,
    month_max: float = 30,
) -> dict[str, Any]:
    from app.screener import screen

    try:
        results = screen(
            days=days,
            low=low,
            high=high,
            month_days=month_days,
            month_max=month_max,
        )
        return {"ok": True, "count": len(results), "stocks": results}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@dataclass
class ToolRegistry:
    tools: dict[str, Callable[..., dict[str, Any]]] | None = None

    def __post_init__(self) -> None:
        if self.tools is None:
            self.tools = {
                "get_stock_price": get_stock_price,
                "get_stock_info": get_stock_info,
                "get_financial_indicators": get_financial_indicators,
                "get_stock_news": get_stock_news,
                "get_market_sentiment": get_market_sentiment,
                "get_global_news": get_global_news,
                "screen_stocks": screen_stocks,
            }

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return get_tool_definitions()

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = (self.tools or {}).get(name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            return tool(**arguments)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
