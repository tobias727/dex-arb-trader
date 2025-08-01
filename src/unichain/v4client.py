import csv
import os
import time
from datetime import datetime
from web3 import Web3
from src.unichain.uniswap_v4_helper import get_amounts_out, get_amounts_in
from src.utils.retrieveAbi import load_contract
from src.config import (
    ALCHEMY_UNICHAIN_BASE_RPC_URL,
    ALCHEMY_API_KEY,
    UNICHAIN_UNISWAP_V4_QUOTER,
    CHAINID_UNICHAIN,
)


class V4Params:
    """Struct for v4 params"""

    def __init__(
        self,
        token_in: str,
        token_out: str,
        amounts_in: list[float],
        pool_fee: int,
        pool_tick_spacing: int,
        pool_hooks: str = "0x0000000000000000000000000000000000000000",
    ):
        self.token_in = token_in
        self.token_out = token_out
        self.amounts_in = amounts_in
        self.pool_fee = pool_fee
        self.pool_tick_spacing = pool_tick_spacing
        self.pool_hooks = pool_hooks


class UnichainV4Client:
    """Stream data from Unichain"""

    def __init__(self, uniswap_v4_params: V4Params, logger):
        # web3 connection
        rpc_url = f"{ALCHEMY_UNICHAIN_BASE_RPC_URL}{ALCHEMY_API_KEY}"
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self._check_web3_connection()
        # swap params
        self.uniswap_v4_params = uniswap_v4_params
        # setup
        self.logger = logger
        self.is_streaming = False
        self.collected_blocks = []
        # load contracts
        self.uniswap_v4_quoter_contract = load_contract(
            self.logger, UNICHAIN_UNISWAP_V4_QUOTER, CHAINID_UNICHAIN, self.web3
        )

    def _check_web3_connection(self):
        if not self.web3.is_connected():
            raise ConnectionError("Could not establish a connection with Alchemy RPC")

    def _get_swap_rates(self):
        """
        Returns bidirectional rates for swapping token pair,
        given amount of token0 (token0_amounts):
        token0->token1 (token1_output),
        token1->token0 (token1_input)
        """
        token1_amounts_out = []
        token1_amounts_in = []
        for token0_amount in self.uniswap_v4_params.amounts_in:
            token1_amount_out = get_amounts_out(
                self.uniswap_v4_quoter_contract,
                self.uniswap_v4_params.token_in,
                self.uniswap_v4_params.token_out,
                token0_amount,
                self.uniswap_v4_params.pool_fee,
                self.uniswap_v4_params.pool_tick_spacing,
            )
            token1_amount_in = get_amounts_in(
                self.uniswap_v4_quoter_contract,
                self.uniswap_v4_params.token_in,
                self.uniswap_v4_params.token_out,
                token0_amount,
                self.uniswap_v4_params.pool_fee,
                self.uniswap_v4_params.pool_tick_spacing,
            )
            token1_amounts_out.append(token1_amount_out)
            token1_amounts_in.append(token1_amount_in)
        return {
            "token0_amounts": self.uniswap_v4_params.amounts_in,
            "token1_outputs": token1_amounts_out,
            "token1_inputs": token1_amounts_in,
        }

    def start_stream(self, duration=5):
        """Method to stream blocks periodically and append to self.collected_blocks"""
        # setup
        is_streaming = True
        current_block = 0
        start_time = time.time()
        while is_streaming:
            try:
                if duration and time.time() - start_time >= duration:
                    is_streaming = False
                    self.logger.info("✅ Terminated Unichain data stream")
                    break
                latest_block = self.web3.eth.get_block("latest")
                # only include new blocks
                if latest_block["number"] > current_block:
                    self.logger.info(f"New block detected: {latest_block['number']}")
                    # compute rates and append data
                    swap_rates = self._get_swap_rates()
                    swap_rates["timestamp"] = latest_block["timestamp"]
                    self.collected_blocks.append(swap_rates)
                    current_block = latest_block["number"]
            except Exception as e:
                self.logger.error(f"❌ Error during stream_blocks: {e}")

    def save_to_csv(self, output_path):
        """Save data to csv"""
        # skip if no data to save
        if not self.collected_blocks:
            self.logger.info("No blocks to save.")
            return

        # unique output file name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(
            output_path, f"{timestamp}_unichain_uniswap_v4_blocks.csv"
        )

        try:
            headers = self.collected_blocks[0].keys()
            with open(output_file, mode="w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(self.collected_blocks)
                self.logger.info(f"📁 Saved collected block data to {output_file}")
        except Exception as e:
            self.logger.error(f"❌ Error saving to CSV: {e}")
