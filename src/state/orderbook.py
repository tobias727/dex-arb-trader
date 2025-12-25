from dataclasses import dataclass


@dataclass(slots=True)
class OrderBook:
    """Holds the state of a Binance order book"""

    bid_sqrt_x96: int | None = None
    ask_sqrt_x96: int | None = None
    bid_price: float | None = None
    ask_price: float | None = None
    bid_qty: float | None = None
    ask_qty: float | None = None
