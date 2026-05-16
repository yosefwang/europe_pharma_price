"""Delegate registry — maps country codes to delegate classes."""

from .base import BaseDelegate
from .france import FranceDelegate
from .ireland import IrelandDelegate
from .poland import PolandDelegate

DELEGATES: dict[str, type[BaseDelegate]] = {
    "IE": IrelandDelegate,
    "PL": PolandDelegate,
    "FR": FranceDelegate,
}


def get_delegate(country_code: str) -> type[BaseDelegate]:
    cc = country_code.upper()
    if cc not in DELEGATES:
        raise KeyError(f"No delegate registered for country code: {country_code}")
    return DELEGATES[cc]
