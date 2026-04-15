from app.market_data.providers.mock import MockMarketDataProvider
from app.strategy.engine import evaluate_strategy
from app.strategy.schemas import StrategyRule
from conftest import client


def test_strategy_engine_is_deterministic() -> None:
    provider = MockMarketDataProvider()
    candles = provider.get_candles(symbol="ETHUSD", asset_class="crypto", timeframe="1h", limit=200)
    rules = [
        StrategyRule(rule_type="volatility_max", params={"lookback": 20, "max_volatility": 0.5}),
        StrategyRule(rule_type="rsi_threshold", params={"period": 14, "threshold": 40, "mode": "above"}),
    ]

    first = evaluate_strategy(candles, rules)
    second = evaluate_strategy(candles, rules)

    assert first.should_signal == second.should_signal
    assert first.score == second.score
    assert first.fired_rules == second.fired_rules


def test_create_strategy_and_scan() -> None:
    create_response = client.post(
        "/strategies",
        json={
            "name": "ETH momentum baseline",
            "symbol": "ETHUSD",
            "asset_class": "crypto",
            "timeframe": "1h",
            "cooldown_minutes": 5,
            "rules": [
                {"rule_type": "volatility_max", "params": {"lookback": 20, "max_volatility": 1.0}},
                {"rule_type": "rsi_threshold", "params": {"period": 14, "threshold": 10, "mode": "above"}},
            ],
        },
    )
    assert create_response.status_code == 201
    strategy = create_response.json()

    scan_response = client.post(f"/strategies/{strategy['id']}/scan")
    assert scan_response.status_code == 200
    payload = scan_response.json()
    assert payload["generated"] is True
    assert payload["signal"]["strategy_id"] == strategy["id"]

    cooldown_scan_response = client.post(f"/strategies/{strategy['id']}/scan")
    assert cooldown_scan_response.status_code == 200
    assert cooldown_scan_response.json()["generated"] is False


def test_list_signals() -> None:
    response = client.get("/strategies/signals")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
