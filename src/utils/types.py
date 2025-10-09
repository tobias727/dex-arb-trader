from dataclasses import dataclass
from typing import Optional


@dataclass
class NotionalValues:
    """Struct for notional values"""

    b_bid: int
    b_ask: int
    u_bid: int
    u_ask: int


@dataclass
class InputAmounts:
    """Struct for input values"""

    binance_buy: Optional[float]
    binance_sell: Optional[float]
    uniswap_buy: Optional[float]
    uniswap_sell: Optional[float]
