import asyncio
import os
import csv
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from web3 import Web3
from src.config import UNISWAP_PROTOCOL_VERSION

from src.config import (
    ALCHEMY_UNICHAIN_BASE_RPC_URL,
    ALCHEMY_UNICHAIN_SEPOLIA_RPC_URL,
    ALCHEMY_API_KEY,
)


class BaseUnichainClient(ABC):
    """Base class for Unichain clients"""

    def __init__(self, logger, testnet: bool = False):
        alchemy_base_rpc_url = (
            ALCHEMY_UNICHAIN_SEPOLIA_RPC_URL
            if testnet
            else ALCHEMY_UNICHAIN_BASE_RPC_URL
        )
        alchemy_api_key = "" if testnet else ALCHEMY_API_KEY
        rpc_url = f"{alchemy_base_rpc_url}{alchemy_api_key}"
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not testnet:
            self._check_web3_connection()  # for testnet always False
        self.logger = logger
        self.is_streaming = False

    def _check_web3_connection(self):
        if not self.web3.is_connected():
            raise ConnectionError("Could not establish a connection with Alchemy RPC")

    @abstractmethod
    async def _get_swap_rates(self):
        pass

    def start_stream(self, output_path, duration=5, latest=False):
        """Method to stream blocks periodically and append to self.collected_blocks"""
        is_streaming = True
        current_block = 0
        start_time = datetime.now()

        # prepare output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(
            output_path,
            (
                f"latest_unichain_uniswap_{UNISWAP_PROTOCOL_VERSION}.csv"
                if latest
                else f"{timestamp}_unichain_uniswap_{UNISWAP_PROTOCOL_VERSION}.csv"
            ),
        )
        headers = [
            "block_number",
            "timestamp",
            "pool_id",
            "feeTier",
            "token0_symbol",
            "token1_symbol",
            "amount_in",
            "bid",
            "bid_gas",
            "ask",
            "ask_gas",
        ]
        csv_file = open(output_file, mode="w", newline="", encoding="utf-8")
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        csv_file.flush()

        async def process_new_block(latest_block):
            """Process data for all pools in the current block"""
            block_number = latest_block["number"]
            self.logger.info(f"🔗 New block detected: {block_number}")
            swap_rates = await self._get_swap_rates()
            for pool_data in swap_rates:
                pool_data["block_number"] = block_number
                pool_data["timestamp"] = latest_block["timestamp"]
                block_level_data = {
                    "block_number": pool_data.get("block_number"),
                    "timestamp": pool_data.get("timestamp"),
                    "pool_id": pool_data.get("pool_id"),
                    "feeTier": pool_data.get("feeTier"),
                    "token0_symbol": pool_data.get("token0.symbol"),
                    "token1_symbol": pool_data.get("token1.symbol"),
                }

                # Flatten rates data
                if pool_data.get("rates") and isinstance(pool_data["rates"], dict):
                    for amount_in, rate_data in pool_data["rates"].items():
                        try:
                            bid_data = rate_data.get("bid", [None, None])
                            ask_data = rate_data.get("ask", [None, None])

                            # Write row to CSV
                            writer.writerow(
                                {
                                    **block_level_data,
                                    "amount_in": amount_in,
                                    "bid": (
                                        bid_data[0]
                                        if isinstance(bid_data, list)
                                        else None
                                    ),
                                    "bid_gas": (
                                        bid_data[1]
                                        if isinstance(bid_data, list)
                                        else None
                                    ),
                                    "ask": (
                                        ask_data[0]
                                        if isinstance(ask_data, list)
                                        else None
                                    ),
                                    "ask_gas": (
                                        ask_data[1]
                                        if isinstance(ask_data, list)
                                        else None
                                    ),
                                }
                            )
                            csv_file.flush()  # Ensure each row is saved immediately
                        except Exception as e:
                            self.logger.error(
                                f"❌ Error while processing rates data: {e}"
                            )
                else:
                    self.logger.warning(
                        f"⚠️ No valid rates data for block: {block_number}"
                    )

        async def block_monitor():
            """Monitor for new blocks and process them"""
            nonlocal current_block, is_streaming
            while is_streaming:
                try:
                    if duration and datetime.now() - start_time >= timedelta(
                        seconds=duration
                    ):
                        is_streaming = False
                        self.logger.info("✅ Terminated Unichain data stream")
                        break
                    # process new blocks
                    latest_block = self.web3.eth.get_block("latest")
                    if latest_block["number"] > current_block:
                        current_block = latest_block["number"]
                        await process_new_block(latest_block)
                except Exception as e:
                    self.logger.error(f"❌ Error during stream_blocks: {e}")
                await asyncio.sleep(0.3)  # Poll for new blocks at regular intervals

        # Run asynchronous block monitoring
        asyncio.run(block_monitor())
