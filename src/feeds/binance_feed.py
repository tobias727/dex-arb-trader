import struct
import math
from state.orderbook import OrderBook


_BBA_STRUCT = struct.Struct("<qqbbqqqq")  # offset=8
Q96 = 2**96
DEC0 = 18  # ETH
DEC1 = 6  # USDC
SCALE = 10 ** (DEC0 - DEC1)


class BinanceDepthFeed:
    """Processes Binance feed messages and updates orderbook state"""

    __slots__ = (
        "orderbook",
        "logger",
    )

    def __init__(self, orderbook: OrderBook, logger):
        self.orderbook = orderbook
        self.logger = logger

    def process(self, raw_msg: bytes):
        """Process a raw message from main.feed_loop and updates order book"""
        ob = self.orderbook
        (
            ob.bid_sqrt_x96,
            ob.ask_sqrt_x96,
            ob.bid_price,
            ob.ask_price,
            ob.bid_qty,
            ob.ask_qty,
        ) = self.decode_best_bid_ask(raw_msg)

    @staticmethod
    def decode_best_bid_ask(raw: bytes):
        """
        Decode byte stream, ref.:
        https://github.com/binance/binance-spot-api-docs/blob/master/sbe/schemas/stream_1_0.xml#L71
        """
        (
            _event_time_us,  # int64
            _book_update_id,  # int64
            price_exp,  # int8
            qty_exp,  # int8
            bid_mantissa,  # int64
            bid_qty_mantissa,  # int64
            ask_mantissa,  # int64
            ask_qty_mantissa,  # int64
        ) = _BBA_STRUCT.unpack_from(raw, 8)

        price_factor = 10.0**price_exp
        qty_factor = 10.0**qty_exp

        # price
        bid_price_h = bid_mantissa * price_factor
        ask_price_h = ask_mantissa * price_factor

        bid_raw = bid_price_h / SCALE
        ask_raw = ask_price_h / SCALE

        bid_sqrt_x96 = int(math.sqrt(bid_raw) * Q96)
        ask_sqrt_x96 = int(math.sqrt(ask_raw) * Q96)

        # qty
        bid_qty = bid_qty_mantissa * qty_factor
        ask_qty = ask_qty_mantissa * qty_factor

        return bid_sqrt_x96, ask_sqrt_x96, bid_price_h, ask_price_h, bid_qty, ask_qty
