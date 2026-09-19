"""MetaTrader 5 integration for Phase 3."""

from ia_financeira.mt5.client import MT5Client, MT5UnavailableError, mt5_package_available, probe_mt5
from ia_financeira.mt5.execution import OrderExecutor, OrderIntent, build_order_intent

__all__ = [
    "MT5Client",
    "MT5UnavailableError",
    "OrderExecutor",
    "OrderIntent",
    "build_order_intent",
    "mt5_package_available",
    "probe_mt5",
]
