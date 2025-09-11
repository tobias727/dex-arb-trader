import sys
import requests
from src.config import (
    BINANCE_BASE_URL_RPC,
    ACTIVE_TRADING_PAIR,
    TOKEN1_DECIMALS,
)

class BinanceClientRpc:
    """Client to receive price and execute via RPC"""
    def __init__(self, logger):
        self.logger = logger
        self.binance_rpc_url = f"{BINANCE_BASE_URL_RPC}/api/v3/depth?symbol={ACTIVE_TRADING_PAIR}&limit=5"

    def get_price(self):
        """Returns top of the order book (int(bid), int(ask))"""
        try:
            r = requests.get(self.binance_rpc_url, timeout=10)
            r.raise_for_status()
        # binance api has rate limit
        except requests.exceptions.HTTPError:
            if r.status_code in (418, 429):
                self.logger.info(f"❌ Rate limit hit ({r.status_code}), stopping bot!")
                sys.exit(1)
            else:
                raise

        data = r.json()
        best_bid_scaled = int(float(data["bids"][0][0]) * 10**TOKEN1_DECIMALS)
        best_ask_scaled = int(float(data["asks"][0][0]) * 10**TOKEN1_DECIMALS)
        return best_bid_scaled, best_ask_scaled
