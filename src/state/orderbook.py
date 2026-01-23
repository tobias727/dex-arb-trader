from dataclasses import dataclass


@dataclass(slots=True)
class OrderBook:
    """Holds the state of a Binance order book.

    Units:
    bid_price / ask_price: price (USDC/ETH)
        - example: 3_000.05
    bid_qty / ask_qty: base asset quantity (ETH)
        - example: 0.5
    """

    bid_price: float | None = None
    ask_price: float | None = None
    bid_qty: float | None = None
    ask_qty: float | None = None
