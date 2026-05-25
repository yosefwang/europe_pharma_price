"""Delegate registry — maps country codes to delegate classes."""

from .base import BaseDelegate
from .belgium import BelgiumDelegate
from .czechia import CzechiaDelegate
from .france import FranceDelegate
from .ireland import IrelandDelegate
from .italy import ItalyDelegate
from .poland import PolandDelegate
from .portugal import PortugalDelegate
from .spain import SpainDelegate

DELEGATES: dict[str, type[BaseDelegate]] = {
    "BE": BelgiumDelegate,
    "CZ": CzechiaDelegate,
    "IE": IrelandDelegate,
    "PL": PolandDelegate,
    "FR": FranceDelegate,
    "ES": SpainDelegate,
    "IT": ItalyDelegate,
    "PT": PortugalDelegate,
}


def get_delegate(country_code: str) -> type[BaseDelegate]:
    cc = country_code.upper()
    if cc not in DELEGATES:
        raise KeyError(f"No delegate registered for country code: {country_code}")
    return DELEGATES[cc]
