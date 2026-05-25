"""Country delegate framework."""

from .base import BaseDelegate, DelegateResult, DelegateState
from .belgium import BelgiumDelegate
from .france import FranceDelegate
from .ireland import IrelandDelegate
from .poland import PolandDelegate
from .registry import DELEGATES, get_delegate

__all__ = [
    "DELEGATES",
    "BaseDelegate",
    "BelgiumDelegate",
    "DelegateResult",
    "DelegateState",
    "FranceDelegate",
    "IrelandDelegate",
    "PolandDelegate",
    "get_delegate",
]
