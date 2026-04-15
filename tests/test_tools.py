import pandas as pd

from app.tools import ToolRegistry, get_stock_price, get_tool_definitions, infer_market


def test_infer_market_from_a_share_code():
    assert infer_market("600519") == "sh"
    assert infer_market("000001") == "sz"
    assert infer_market("300750") == "sz"


def test_get_tool_definitions_includes_screener():
    names = [tool["function"]["name"] for tool in get_tool_definitions()]
    assert "screen_stocks" in names


def test_tool_registry_returns_error_payload_on_failure():
    registry = ToolRegistry(
        {"boom": lambda **_: (_ for _ in ()).throw(ValueError("bad input"))}
    )

    result = registry.call("boom", {})

    assert result["ok"] is False
    assert "bad input" in result["error"]


def test_get_stock_price_falls_back_to_secondary_source(monkeypatch):
    def fail_primary(**kwargs):
        raise ConnectionError("primary source failed")

    def ok_fallback(**kwargs):
        return pd.DataFrame(
            [
                {"日期": "2024-01-01", "收盘": 10.0},
                {"日期": "2024-01-02", "收盘": 10.5},
            ]
        )

    monkeypatch.setattr("app.tools.ak.stock_zh_a_hist", fail_primary)
    monkeypatch.setattr("app.tools.ak.stock_zh_a_hist_tx", ok_fallback)

    result = get_stock_price("600519", limit=1)

    assert result["ok"] is True
    assert result["source"] == "stock_zh_a_hist_tx"
    assert len(result["rows"]) == 1
