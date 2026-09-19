from __future__ import annotations

from ia_financeira.config import Settings
from ia_financeira.mt5.execution import OrderExecutor, build_order_intent
from ia_financeira.tools.market_data import MarketDataProvider, MarketSnapshot


def test_build_order_intent_buy_uses_atr_stops():
    snap = MarketSnapshot(
        ticker="PETR4",
        mode="stub",
        rsi_14=28.0,
        ma_200=49.0,
        price_vs_ma200="Abaixo da Média",
        atr_14=1.0,
        bid=48.0,
        ask=48.1,
        last=48.05,
        digits=2,
    )
    cfg = Settings(mt5_volume=0.01, mt5_sl_atr_mult=1.5, mt5_tp_atr_mult=2.5, mt5_dry_run=True)
    intent = build_order_intent(action="COMPRA", snapshot=snap, confidence=80, cfg=cfg)
    assert intent is not None
    assert intent.side == "buy"
    assert intent.entry_price == 48.1
    assert intent.stop_loss == round(48.1 - 1.5, 2)
    assert intent.take_profit == round(48.1 + 2.5, 2)
    assert intent.dry_run is True


def test_executor_dry_run_never_sends():
    snap = MarketSnapshot(
        ticker="PETR4",
        mode="stub",
        rsi_14=28.0,
        ma_200=49.0,
        price_vs_ma200="Abaixo da Média",
        atr_14=1.0,
        bid=48.0,
        ask=48.1,
        last=48.05,
        digits=2,
    )
    # Even with dry_run false, without allow_demo_orders must stay dry-run
    cfg = Settings(mt5_dry_run=False, mt5_allow_demo_orders=False)
    intent = build_order_intent(action="VENDA", snapshot=snap, confidence=90, cfg=cfg)
    assert intent is not None
    assert intent.dry_run is True
    result = OrderExecutor(cfg).execute(intent)
    assert result["status"] == "dry_run"
    assert result["would_send"] is True
    assert result["intent"]["side"] == "sell"


def test_can_send_requires_both_flags():
    locked = Settings(mt5_dry_run=True, mt5_allow_demo_orders=True)
    assert locked.can_send_mt5_orders() is False
    demo = Settings(mt5_dry_run=False, mt5_allow_demo_orders=True)
    assert demo.can_send_mt5_orders() is True


def test_market_stub_mode():
    snap = MarketDataProvider(Settings(market_data_mode="stub")).snapshot("PETR4")
    assert snap.mode == "stub"
    assert snap.rsi_14 == 28.0
    assert "RSI_14" in snap.as_context_block()


def test_auto_mode_falls_back_without_mt5():
    snap = MarketDataProvider(Settings(market_data_mode="auto")).snapshot("WIN$")
    assert snap.mode in {"stub", "stub-fallback"}
    assert snap.atr_14 > 0
