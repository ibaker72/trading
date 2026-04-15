from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from app.market_data.schemas import MarketCandle
from app.strategy.schemas import StrategyRule


@dataclass
class EvaluationResult:
    should_signal: bool
    score: float
    fired_rules: list[str]


def evaluate_strategy(candles: list[MarketCandle], rules: list[StrategyRule]) -> EvaluationResult:
    if len(candles) < 20:
        return EvaluationResult(should_signal=False, score=0.0, fired_rules=[])

    fired: list[str] = []

    for rule in rules:
        if not rule.enabled:
            continue
        if _evaluate_rule(candles, rule):
            fired.append(rule.rule_type)

    active_rules = [rule for rule in rules if rule.enabled]
    if not active_rules:
        return EvaluationResult(should_signal=False, score=0.0, fired_rules=[])

    score = len(fired) / len(active_rules)
    should_signal = len(fired) == len(active_rules)
    return EvaluationResult(should_signal=should_signal, score=round(score, 4), fired_rules=fired)


def _evaluate_rule(candles: list[MarketCandle], rule: StrategyRule) -> bool:
    latest = candles[-1]

    if rule.rule_type == "price_breakout":
        lookback = int(rule.params.get("lookback", 20))
        previous_high = max(candle.high for candle in candles[-(lookback + 1) : -1])
        return latest.close > previous_high

    if rule.rule_type == "ma_cross":
        fast = int(rule.params.get("fast", 9))
        slow = int(rule.params.get("slow", 21))
        if slow <= fast or len(candles) < slow + 2:
            return False

        prev_fast = _sma(candles[:-1], fast)
        prev_slow = _sma(candles[:-1], slow)
        curr_fast = _sma(candles, fast)
        curr_slow = _sma(candles, slow)
        return prev_fast <= prev_slow and curr_fast > curr_slow

    if rule.rule_type == "rsi_threshold":
        period = int(rule.params.get("period", 14))
        threshold = float(rule.params.get("threshold", 50.0))
        mode = str(rule.params.get("mode", "above"))
        rsi = _rsi(candles, period)
        if rsi is None:
            return False
        if mode == "below":
            return rsi < threshold
        return rsi > threshold

    if rule.rule_type == "volume_spike":
        lookback = int(rule.params.get("lookback", 20))
        multiplier = float(rule.params.get("multiplier", 1.5))
        avg_volume = sum(candle.volume for candle in candles[-(lookback + 1) : -1]) / lookback
        return latest.volume > avg_volume * multiplier

    if rule.rule_type == "volatility_max":
        lookback = int(rule.params.get("lookback", 20))
        max_volatility = float(rule.params.get("max_volatility", 0.03))
        vol = _stddev_returns(candles[-lookback:])
        return vol <= max_volatility

    if rule.rule_type == "gap_up":
        min_gap_pct = float(rule.params.get("min_gap_pct", 0.02))
        if len(candles) < 2:
            return False
        first_close = candles[0].close
        if first_close == 0:
            return False
        gap = (latest.open - first_close) / first_close
        return gap >= min_gap_pct

    if rule.rule_type == "gap_down":
        min_gap_pct = float(rule.params.get("min_gap_pct", 0.02))
        if len(candles) < 2:
            return False
        first_close = candles[0].close
        if first_close == 0:
            return False
        gap = (latest.open - first_close) / first_close
        return gap <= -min_gap_pct

    if rule.rule_type == "vwap_cross":
        if len(candles) < 2:
            return False
        vwap = _vwap(candles)
        prev_close = candles[-2].close
        curr_close = candles[-1].close
        return prev_close < vwap and curr_close > vwap

    if rule.rule_type == "ema_cross":
        fast = int(rule.params.get("fast", 9))
        slow = int(rule.params.get("slow", 21))
        if len(candles) < slow + 2:
            return False
        prev_fast = _ema(candles[:-1], fast)
        prev_slow = _ema(candles[:-1], slow)
        curr_fast = _ema(candles, fast)
        curr_slow = _ema(candles, slow)
        return prev_fast <= prev_slow and curr_fast > curr_slow

    return False


def _sma(candles: list[MarketCandle], period: int) -> float:
    closes = [candle.close for candle in candles[-period:]]
    return sum(closes) / len(closes)


def _ema(candles: list[MarketCandle], period: int) -> float:
    closes = [candle.close for candle in candles]
    if not closes:
        return 0.0
    smoothing = 2.0 / (period + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = price * smoothing + ema * (1 - smoothing)
    return ema


def _vwap(candles: list[MarketCandle]) -> float:
    total_volume = sum(candle.volume for candle in candles)
    if total_volume == 0:
        return 0.0
    cumulative = sum(
        ((candle.high + candle.low + candle.close) / 3) * candle.volume
        for candle in candles
    )
    return cumulative / total_volume


def _rsi(candles: list[MarketCandle], period: int) -> float | None:
    if len(candles) < period + 1:
        return None
    closes = [candle.close for candle in candles[-(period + 1) :]]
    gains = []
    losses = []

    for prev, curr in zip(closes, closes[1:]):
        delta = curr - prev
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(delta))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _stddev_returns(candles: list[MarketCandle]) -> float:
    closes = [candle.close for candle in candles]
    returns = [(curr - prev) / prev for prev, curr in zip(closes, closes[1:]) if prev != 0]
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((ret - mean) ** 2 for ret in returns) / len(returns)
    return sqrt(variance)
