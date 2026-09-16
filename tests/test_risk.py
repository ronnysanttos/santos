"""Testes de gestão de risco / sizing (sem MT5)."""

from __future__ import annotations

from datetime import datetime

from mt5_ea.risk import (
    ContractSpec,
    RiskContext,
    RiskManager,
    RiskParams,
    in_trading_session,
    money_at_risk_per_lot,
    normalize_volume,
    size_by_risk_percent,
    spread_points,
)
from mt5_ea.strategy import Signal


def _fx_contract() -> ContractSpec:
    # EURUSD típico: point=0.00001, tick_size=0.00001, tick_value≈1.0 por lote padrão
    return ContractSpec(
        point=0.00001,
        digits=5,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        tick_size=0.00001,
        tick_value=1.0,
    )


def _ctx(**overrides) -> RiskContext:
    base = dict(
        equity=10_000.0,
        balance=10_000.0,
        bid=1.10000,
        ask=1.10020,
        open_positions=0,
        open_side=None,
        daily_pnl=0.0,
        now=datetime(2024, 6, 3, 12, 0, 0),  # segunda 12h
        contract=_fx_contract(),
    )
    base.update(overrides)
    return RiskContext(**base)  # type: ignore[arg-type]


def test_normalize_volume_rounds_to_step() -> None:
    assert normalize_volume(0.019, volume_min=0.01, volume_max=1.0, volume_step=0.01) == 0.01
    assert normalize_volume(0.004, volume_min=0.01, volume_max=1.0, volume_step=0.01) == 0.0
    assert normalize_volume(1.5, volume_min=0.01, volume_max=1.0, volume_step=0.01) == 1.0


def test_money_at_risk_and_percent_sizing() -> None:
    # 150 pontos de SL (0.00150) → 150 ticks → $150 / lote
    per_lot = money_at_risk_per_lot(1.10000, 1.09850, tick_size=0.00001, tick_value=1.0)
    assert abs(per_lot - 150.0) < 1e-9

    # risk 0.5% de 10k = $50 → 50/150 ≈ 0.333 → 0.33 lotes
    vol = size_by_risk_percent(10_000.0, 0.5, 1.10000, 1.09850, _fx_contract())
    assert vol == 0.33


def test_spread_filter_blocks_entry() -> None:
    rm = RiskManager(RiskParams(max_spread_points=10, session_start_hour=None, session_end_hour=None))
    signal = Signal(
        action="enter_long",
        reason="test",
        entry_price=1.10020,
        stop_loss=1.09800,
        take_profit=1.10400,
    )
    # spread = 0.00040 / 0.00001 = 40 pontos
    decision = rm.decide(signal, _ctx(bid=1.10000, ask=1.10040))
    assert decision.action == "skip"
    assert "spread" in decision.reason.lower()


def test_daily_loss_blocks_entry() -> None:
    rm = RiskManager(
        RiskParams(
            max_daily_loss_percent=2.0,
            session_start_hour=None,
            session_end_hour=None,
            max_spread_points=0,
        )
    )
    signal = Signal(
        action="enter_long",
        reason="test",
        entry_price=1.10020,
        stop_loss=1.09800,
        take_profit=1.10400,
    )
    decision = rm.decide(signal, _ctx(daily_pnl=-250.0, balance=10_000.0))
    assert decision.action == "skip"
    assert "perda diária" in decision.reason.lower()


def test_session_filter_blocks_entry_allows_exit() -> None:
    rm = RiskManager(
        RiskParams(
            session_start_hour=7,
            session_end_hour=21,
            max_spread_points=0,
            max_daily_loss_percent=0,
        )
    )
    enter = Signal(
        action="enter_long",
        reason="entrada",
        entry_price=1.10020,
        stop_loss=1.09800,
        take_profit=1.10400,
    )
    night = _ctx(now=datetime(2024, 6, 3, 23, 0, 0))
    assert rm.decide(enter, night).action == "skip"

    exit_sig = Signal(action="exit_long", reason="saída")
    night_long = _ctx(now=datetime(2024, 6, 3, 23, 0, 0), open_side="buy", open_positions=1)
    assert rm.decide(exit_sig, night_long).action == "exit_long"


def test_max_positions_and_fixed_lots() -> None:
    rm = RiskManager(
        RiskParams(
            mode="fixed",
            fixed_lots=0.02,
            max_positions=1,
            session_start_hour=None,
            session_end_hour=None,
            max_spread_points=0,
            max_daily_loss_percent=0,
        )
    )
    signal = Signal(
        action="enter_short",
        reason="short",
        entry_price=1.10000,
        stop_loss=1.10200,
        take_profit=1.09600,
    )
    blocked = rm.decide(signal, _ctx(open_positions=1, open_side="buy"))
    assert blocked.action == "skip"

    ok = rm.decide(signal, _ctx())
    assert ok.action == "enter_short"
    assert ok.volume == 0.02
    assert ok.stop_loss == 1.10200


def test_in_trading_session_overnight() -> None:
    now = datetime(2024, 1, 1, 23, 30, 0)
    assert in_trading_session(now, 22, 6) is True
    assert in_trading_session(now, 7, 21) is False


def test_spread_points() -> None:
    assert abs(spread_points(1.1, 1.10025, 0.00001) - 25.0) < 1e-9
