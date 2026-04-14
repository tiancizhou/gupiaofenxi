from app.tools import ToolRegistry, get_tool_definitions, infer_market


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
