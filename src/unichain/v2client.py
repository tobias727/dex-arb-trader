import csv
import os
import time
from datetime import datetime
from typing import List
from web3 import Web3
from src.unichain.uniswap_v2_helper import get_amounts_out, get_amounts_in
from src.utils.retrieveAbi import load_contract
from src.config import (
    ALCHEMY_UNICHAIN_BASE_RPC_URL,
    ALCHEMY_API_KEY,
    UNICHAIN_UNISWAP_V2_ROUTER_02,
    CHAINID_UNICHAIN,
)


class UnichainClient:
    """Stream data from Unichain"""

    def __init__(
        self,
        token0: str,
        token1: str,
        token0_amounts: List[float],
        logger,
    ):
        # web3 connection
        rpc_url = f"{ALCHEMY_UNICHAIN_BASE_RPC_URL}{ALCHEMY_API_KEY}"
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self._check_web3_connection()
        # swap params
        self.token0 = token0
        self.token1 = token1
        self.token0_amounts = token0_amounts
        # setup
        self.logger = logger
        self.is_streaming = False
        self.collected_blocks = []
        # load contracts
        self.uniswap_v2_router_contract = load_contract(
            self.logger, UNICHAIN_UNISWAP_V2_ROUTER_02, CHAINID_UNICHAIN, self.web3
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
        for token0_amount in self.token0_amounts:
            token1_amount_out = get_amounts_out(
                self.uniswap_v2_router_contract,
                self.token0,
                self.token1,
                token0_amount,
            )
            token1_amount_in = get_amounts_in(
                self.uniswap_v2_router_contract,
                self.token1,
                self.token0,
                token0_amount,
            )
            token1_amounts_out.append(token1_amount_out)
            token1_amounts_in.append(token1_amount_in)
        return {
            "token0_amounts": self.token0_amounts,
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
            output_path, f"{timestamp}_unichain_uniswap_v2_blocks.csv"
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
