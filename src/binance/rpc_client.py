import sys
import time
import hmac
import hashlib
import requests
from src.config import (
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    BINANCE_API_KEY_TESTNET,
    BINANCE_API_SECRET_TESTNET,
    BINANCE_BASE_URL_RPC,
    ACTIVE_TRADING_PAIR,
    TOKEN1_DECIMALS,
    BINANCE_BASE_URL_RPC_TESTNET,
)


class BinanceClientRpc:
    """Client to receive price and execute via RPC"""

    def __init__(self, logger, token0_input, testnet: bool = False):
        self.logger = logger
        self.binance_rpc_url_quote = (
            f"{BINANCE_BASE_URL_RPC}/api/v3/depth?symbol={ACTIVE_TRADING_PAIR}&limit=5"
        )
        self.token0_input = token0_input
        # handle values for testnet and mainnet, only for execution
        self.binance_rpc_url_trade = f"{BINANCE_BASE_URL_RPC_TESTNET if testnet else BINANCE_BASE_URL_RPC}/api/v3/order"
        self.binance_api_key = BINANCE_API_KEY_TESTNET if testnet else BINANCE_API_KEY
        self.binance_api_secret = (
            BINANCE_API_SECRET_TESTNET if testnet else BINANCE_API_SECRET
        )

    def get_price(self):
        """Returns top of the order book (int(bid), int(ask))"""
        try:
            r = requests.get(self.binance_rpc_url_quote, timeout=10)
            r.raise_for_status()
        # binance api has rate limit
        except requests.exceptions.HTTPError:
            if r.status_code in (418, 429):
                self.logger.info(f"❌ Rate limit hit ({r.status_code}), stopping bot!")
                sys.exit(1)
            else:
                raise

        data = r.json()
        bid_notional = int(
            (float(data["bids"][0][0]) * 10**TOKEN1_DECIMALS) * float(self.token0_input)
        )  # (price in smallest unit) // token0_input
        ask_notional = int(
            (float(data["asks"][0][0]) * 10**TOKEN1_DECIMALS) * float(self.token0_input)
        )
        return bid_notional, ask_notional

    def execute_trade(self, side: str, symbol: str = ACTIVE_TRADING_PAIR):
        """
        Executes binance leg
        Returns 'FILLED' if successful
        """
        api_params = f"symbol={symbol}&side={side.upper()}&type=MARKET&quantity={self.token0_input}&timestamp={int(time.time()*1000)}"  # time in ms
        signed_params = self._sign_payload(api_params)

        headers = {"X-MBX-APIKEY": self.binance_api_key}

        try:
            r = requests.post(
                self.binance_rpc_url_trade,
                headers=headers,
                params=signed_params,
                timeout=10,
            )
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"❌ Failed to execute trade: {e.response.text}")
            raise
        data = r.json()
        self.logger.info(f"✅ Executed Binance {side} order: {data}")
        return data

    def _sign_payload(self, api_params: str) -> dict:
        """Signs the request params with API secret"""
        signature = hmac.new(
            self.binance_api_secret.encode("utf-8"),
            api_params.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{api_params}&signature={signature}"
