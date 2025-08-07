import asyncio
from src.unichain.helpers.uniswap_v4_helper import get_amounts_out, get_amounts_in
from src.utils.retrieve_abi import load_contract
from src.unichain.clients.base_client import BaseUnichainClient
from src.config import (
    UNICHAIN_UNISWAP_V4_QUOTER,
    CHAINID_UNICHAIN,
)


class UnichainV4Client(BaseUnichainClient):
    """Stream data from Unichain"""

    def __init__(self, pools, logger):
        super().__init__(logger)
        # swap params
        self.pools = pools
        # load contracts
        self.uniswap_v4_quoter_contract = load_contract(
            self.logger, UNICHAIN_UNISWAP_V4_QUOTER, CHAINID_UNICHAIN, self.web3
        )

    async def _fetch_pool_rates(self, pool):
        """Fetch rates for a single pool asynchronously"""
        try:
            # dynamic input adjustment
            token0_decimals = int(pool["token0"]["decimals"])
            input_amounts = [10 ** (token0_decimals-2), 10 ** (token0_decimals - 3)]

            pool_result = {
                "pool_id": pool["id"],
                "feeTier": pool["feeTier"],
                "token0.symbol": pool["token0"]["symbol"],
                "token1.symbol": pool["token1"]["symbol"],
                "token0.id": pool["token0"]["id"],
                "token1.id": pool["token1"]["id"],
                "rates": {}
            }
            # Compute rates for each token0 input amount
            for amount_token0 in input_amounts:
                token_out_amount = await asyncio.to_thread(
                    get_amounts_out,
                    self.uniswap_v4_quoter_contract,
                    pool["token0"]["id"],
                    pool["token1"]["id"],
                    amount_token0,
                    int(pool["feeTier"]),
                    int(pool["tickSpacing"]),
                )
                token_in_amount = await asyncio.to_thread(
                    get_amounts_in,
                    self.uniswap_v4_quoter_contract,
                    pool["token0"]["id"],
                    pool["token1"]["id"],
                    amount_token0,
                    int(pool["feeTier"]),
                    int(pool["tickSpacing"]),
                )
                pool_result["rates"][amount_token0] = {
                    "bid": token_out_amount,
                    "ask": token_in_amount,
                }
            return pool_result
        except Exception as e:
            self.logger.error(f"❌ Error fetching swap rates for pool {pool['id']}: {e}")
            return None

    async def _get_swap_rates(self):
        """Fetch swap rates for all pools asynchronously"""
        tasks = [self._fetch_pool_rates(pool) for pool in self.pools]
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)
        # Filter out any failed requests (None results)
        return [result for result in results if result is not None]
