import time
import os
import csv
from abc import ABC, abstractmethod
from datetime import datetime
from web3 import Web3
from src.config import UNISWAP_PROTOCOL_VERSION

from src.config import (
    ALCHEMY_UNICHAIN_BASE_RPC_URL,
    ALCHEMY_API_KEY,
)


class BaseUnichainClient(ABC):
    """Base class for Unichain clients"""

    def __init__(self, logger):
        rpc_url = f"{ALCHEMY_UNICHAIN_BASE_RPC_URL}{ALCHEMY_API_KEY}"
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self._check_web3_connection()
        self.logger = logger
        self.is_streaming = False
        self.collected_blocks = []

    def _check_web3_connection(self):
        if not self.web3.is_connected():
            raise ConnectionError("Could not establish a connection with Alchemy RPC")

    @abstractmethod
    def _get_swap_rates(self):
        pass

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

    def save_to_csv(self, output_path, latest=False):
        """Save collected block data to a CSV file"""
        # skip if no data to save
        if not self.collected_blocks:
            self.logger.info("No blocks collected to save.")
            return

        # output file name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(
            output_path,
            (
                f"latest_unichain_uniswap_{UNISWAP_PROTOCOL_VERSION}.csv"
                if latest
                else f"{timestamp}_unichain_uniswap_{UNISWAP_PROTOCOL_VERSION}.csv"
            ),
        )

        try:
            headers = self.collected_blocks[0].keys()
            with open(output_file, mode="w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(self.collected_blocks)
            self.logger.info(f"📁 Saved data to {output_file}")
        except Exception as e:
            self.logger.error(f"❌ Error saving to CSV: {e}")
