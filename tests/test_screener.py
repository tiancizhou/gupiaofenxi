from app.screener import calc_pct, infer_market


def test_infer_market():
    assert infer_market("600519") == "sh"
    assert infer_market("000001") == "sz"
    assert infer_market("300750") == "sz"


def test_calc_pct_with_close_key():
    rows = [
        {"日期": "d1", "收盘": "10.0"},
        {"日期": "d2", "收盘": "9.0"},
        {"日期": "d3", "收盘": "8.0"},
    ]
    assert calc_pct(rows, 2) == (8.0 - 10.0) / 10.0 * 100


def test_calc_pct_returns_none_when_too_short():
    rows = [{"收盘": "10.0"}, {"收盘": "9.0"}]
    assert calc_pct(rows, 2) is None
