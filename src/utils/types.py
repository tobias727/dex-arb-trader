from dataclasses import dataclass


@dataclass
class NotionalValues:
    """Struct for notional values"""

    b_bid: int
    b_ask: int
    u_bid: int
    u_ask: int
