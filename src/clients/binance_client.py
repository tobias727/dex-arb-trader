import time
import hmac
from urllib.parse import parse_qsl
import hashlib
import aiohttp
from src.config import (
    TESTNET,
    TOKEN0_INPUT,
    BINANCE_BASE_URL_RPC_TESTNET,
    BINANCE_BASE_URL_RPC,
    BINANCE_API_KEY_TESTNET,
    BINANCE_API_KEY,
    BINANCE_API_SECRET_TESTNET,
    BINANCE_API_SECRET,
)


class BinanceClient:
    """CEX client"""

    def __init__(self, logger):
        self.binance_rpc_url_trade = f"{BINANCE_BASE_URL_RPC_TESTNET if TESTNET else BINANCE_BASE_URL_RPC}/api/v3/order"
        self.binance_rpc_url_account = f"{BINANCE_BASE_URL_RPC_TESTNET if TESTNET else BINANCE_BASE_URL_RPC}/api/v3/account"
        self.binance_api_key = BINANCE_API_KEY_TESTNET if TESTNET else BINANCE_API_KEY
        self.binance_api_secret = (
            BINANCE_API_SECRET_TESTNET if TESTNET else BINANCE_API_SECRET
        )
        self.logger = logger
        self.session = None

    async def init_session(self):
        """Opens connection"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Closes connection"""
        if self.session:
            await self.session.close()

    async def execute_trade(self, side: str):
        """Returns 'FILLED' if successful"""
        api_params = (
            f"symbol=ETHUSDC&side={side.upper()}&type=MARKET"
            f"&quantity={TOKEN0_INPUT}&timestamp={int(time.time()*1000)}"
        )
        signed_params = await self._sign_payload(api_params)
        headers = {"X-MBX-APIKEY": self.binance_api_key}
        async with self.session.post(
            url=self.binance_rpc_url_trade,
            headers=headers,
            params=dict(parse_qsl(signed_params)),
            timeout=10,
        ) as r:
            r.raise_for_status()
            return await r.json()

    async def _sign_payload(self, api_params: str) -> dict:
        """Signs the request params with API secret"""
        signature = hmac.new(
            self.binance_api_secret.encode("utf-8"),
            api_params.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{api_params}&signature={signature}"

    async def get_balances(self):
        """Returns balances for USDC and ETH"""
        api_params = f"timestamp={int(time.time()*1000)}"
        signed_params = await self._sign_payload(api_params)
        headers = {"X-MBX-APIKEY": self.binance_api_key}
        async with self.session.get(
            self.binance_rpc_url_account,
            headers=headers,
            params=signed_params,
            timeout=10,
        ) as r:
            r.raise_for_status()
            account_data = await r.json()

        balance_eth = None
        balance_usdc = None
        for balance in account_data["balances"]:
            asset = balance.get("asset")
            free_amount = balance.get("free")
            locked_amount = balance.get("locked")
            if asset == "ETH":
                balance_eth = free_amount
                if float(locked_amount) > 0:
                    self.logger.warning(
                        "Locked funds in Binance for Asset ETH: %s", locked_amount
                    )
            elif asset == "USDC":
                balance_usdc = free_amount
        return float(balance_eth), float(balance_usdc)
