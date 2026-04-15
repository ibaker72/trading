from datetime import datetime, UTC

from app.market_data.providers.base import MarketDataProvider
from app.market_data.schemas import AssetClass
from app.strategy.engine import evaluate_strategy
from app.strategy.schemas import MultiTimeframeScanResult, StrategyRule, WatchlistScanResult

_BUY_RULES = {"rsi_threshold", "ma_cross", "ema_cross", "vwap_cross", "gap_up", "price_breakout"}
_SELL_RULES = {"gap_down"}


class WatchlistScanner:
    def __init__(
        self,
        provider: MarketDataProvider,
        rules: list[StrategyRule],
        timeframes: list[str] | None = None,
    ) -> None:
        self._provider = provider
        self._rules = rules
        self._timeframes = timeframes or ["5m", "15m", "1h"]

    def scan_symbol(self, symbol: str, asset_class: AssetClass) -> MultiTimeframeScanResult:
        scores: list[float] = []
        fired_timeframes: list[str] = []
        all_fired_rules: list[str] = []

        for tf in self._timeframes:
            try:
                candles = self._provider.get_candles(symbol, asset_class, tf, 200)
            except Exception:
                candles = []

            result = evaluate_strategy(candles, self._rules)
            scores.append(result.score)
            if result.should_signal:
                fired_timeframes.append(tf)
            all_fired_rules.extend(result.fired_rules)

        aggregate_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        should_trade = aggregate_score >= 0.6 and len(fired_timeframes) >= 2

        # Determine suggested side
        buy_votes = sum(1 for r in all_fired_rules if r in _BUY_RULES)
        sell_votes = sum(1 for r in all_fired_rules if r in _SELL_RULES)

        if sell_votes > 0 and "gap_down" in all_fired_rules:
            suggested_side = "sell"
        elif buy_votes > sell_votes:
            suggested_side = "buy"
        else:
            suggested_side = "none"

        return MultiTimeframeScanResult(
            symbol=symbol,
            asset_class=asset_class,
            fired_timeframes=fired_timeframes,
            aggregate_score=aggregate_score,
            should_trade=should_trade,
            suggested_side=suggested_side,
        )

    def scan_watchlist(
        self, symbols: list[tuple[str, AssetClass]]
    ) -> WatchlistScanResult:
        results: list[MultiTimeframeScanResult] = []

        for symbol, asset_class in symbols:
            try:
                result = self.scan_symbol(symbol, asset_class)
                results.append(result)
            except Exception:
                pass

        results.sort(key=lambda r: r.aggregate_score, reverse=True)
        top_pick = next((r for r in results if r.should_trade), None)

        return WatchlistScanResult(
            scanned_at=datetime.now(UTC),
            results=results,
            top_pick=top_pick,
        )
