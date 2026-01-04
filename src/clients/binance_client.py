import time
import asyncio
import ssl
import hmac
from urllib.parse import urlencode
import hashlib
import aiohttp
from config import (
    BINANCE_URI_REST,
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
)


class BinanceClient:
    """CEX client"""

    def __init__(self):
        """Opens HTTPS connection"""
        ssl_context = (
            ssl._create_unverified_context()
        )  # TODO: ssl.create_default_context()
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(
            base_url=BINANCE_URI_REST,
            connector=connector,
            raise_for_status=True,
            headers={"X-MBX-APIKEY": BINANCE_API_KEY},
        )

    async def keep_connection_hot(self, ping_interval: int = 30) -> None:
        """Sends HTTP request to keep TCP/TLS connection alive"""
        while True:
            async with self.session.get("/api/v3/ping") as r:
                await r.read()
            await asyncio.sleep(ping_interval)

    async def get_balances(self) -> tuple:
        """Returns balances for USDC and ETH"""
        params = {"timestamp": int(time.time() * 1000)}
        signed_params = self._sign_params(params)
        async with self.session.get(
            "/api/v3/account",
            params=signed_params,
        ) as r:
            account_data = await r.json()

        bal_map = {b["asset"]: b["free"] for b in account_data.get("balances", [])}

        eth_str = bal_map.get("ETH")
        usdc_str = bal_map.get("USDC")

        return float(eth_str), float(usdc_str)

    async def execute_trade(self, side: str, qty: float) -> dict:
        """Returns 'FILLED' if successful"""
        params = {
            "symbol": "ETHUSDC",
            "side": side.upper(),
            "type": "MARKET",
            "quantity": str(qty),
            "timestamp": int(time.time() * 1000),
        }
        signed_params = self._sign_params(params)
        async with self.session.post(
            "/api/v3/order",
            params=signed_params,
        ) as r:
            return await r.json()

    @staticmethod
    def _sign_params(params: dict) -> dict:
        qs = urlencode(params)
        sig = hmac.new(
            BINANCE_API_SECRET.encode(), qs.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = sig
        return params
