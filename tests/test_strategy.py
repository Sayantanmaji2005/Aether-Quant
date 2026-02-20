from aetherquant.strategy import StrategyConfig, signal


def test_signal_buy() -> None:
    assert signal(0.02, StrategyConfig(threshold=0.01)) == "buy"


def test_signal_hold() -> None:
    assert signal(0.005, StrategyConfig(threshold=0.01)) == "hold"


def test_signal_sell() -> None:
    assert signal(-0.03, StrategyConfig(threshold=0.01)) == "sell"
