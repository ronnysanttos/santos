"""Utilitários de timeframe (M1, M15, H1, …) sem dependência do terminal MT5."""

from __future__ import annotations

import re

# minutos → rótulo canônico
_MINUTES_TO_LABEL: dict[int, str] = {
    1: "M1",
    2: "M2",
    3: "M3",
    4: "M4",
    5: "M5",
    6: "M6",
    10: "M10",
    12: "M12",
    15: "M15",
    20: "M20",
    30: "M30",
    60: "H1",
    120: "H2",
    180: "H3",
    240: "H4",
    360: "H6",
    480: "H8",
    720: "H12",
    1440: "D1",
    10080: "W1",
    43200: "MN1",
}

_LABEL_TO_MINUTES: dict[str, int] = {v: k for k, v in _MINUTES_TO_LABEL.items()}
# aliases extras
_LABEL_TO_MINUTES.update(
    {
        "MN": 43200,
        "MONTH": 43200,
        "D": 1440,
        "W": 10080,
        "H": 60,
    }
)


def parse_timeframe(value: str | int | None, *, default_minutes: int = 15) -> int:
    """
    Converte timeframe para minutos.

    Aceita: 15, "15", "M15", "m15", "H1", "D1", "W1", "MN1".
    """
    if value is None:
        return default_minutes
    if isinstance(value, int):
        if value not in _MINUTES_TO_LABEL:
            raise ValueError(
                f"timeframe {value} min não suportado; use {_sorted_labels()}"
            )
        return value

    raw = str(value).strip().upper()
    if not raw:
        return default_minutes

    if raw.isdigit():
        minutes = int(raw)
        if minutes not in _MINUTES_TO_LABEL:
            raise ValueError(
                f"timeframe {minutes} min não suportado; use {_sorted_labels()}"
            )
        return minutes

    if raw in _LABEL_TO_MINUTES:
        return _LABEL_TO_MINUTES[raw]

    match = re.fullmatch(r"([MHDW]|MN)(\d+)", raw)
    if match:
        unit, num_s = match.group(1), match.group(2)
        num = int(num_s)
        if unit == "M":
            minutes = num
        elif unit == "H":
            minutes = num * 60
        elif unit == "D":
            minutes = num * 1440
        elif unit == "W":
            minutes = num * 10080
        else:  # MN
            minutes = num * 43200
        if minutes in _MINUTES_TO_LABEL:
            return minutes

    raise ValueError(
        f"timeframe inválido: {value!r}. Exemplos: M15, H1, D1 ou minutos "
        f"({_sorted_labels()})"
    )


def timeframe_label(minutes: int) -> str:
    if minutes not in _MINUTES_TO_LABEL:
        raise ValueError(f"timeframe {minutes} min desconhecido")
    return _MINUTES_TO_LABEL[minutes]


def supported_timeframes() -> list[str]:
    return [_MINUTES_TO_LABEL[m] for m in sorted(_MINUTES_TO_LABEL)]


def _sorted_labels() -> str:
    return ", ".join(supported_timeframes())
