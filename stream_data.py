import os
import threading
import logging
import asyncio
from src.unichain.client import UnichainClient
from src.binance.client import BinanceClient
from src.config import (
    OUTPUT_DIRECTORY
)

STREAM_DURATION = 600


def binance_task(binance_client: BinanceClient, output_path, logger, duration):
    """Task to handle Binance WebSocket streaming"""
    logger.info("Starting Binance WebSocket stream...")
    asyncio.run(binance_client.ws_stream(duration))
    binance_client.save_to_csv(output_path)

def unichain_task(unichain_client: UnichainClient, output_path, logger, duration):
    """Task to handle Unichain data streaming"""
    logger.info("Starting Unichain data stream...")
    unichain_client.start_stream(duration)
    unichain_client.save_to_csv(output_path)

def main():
    """Main class to stream data"""
    # setup
    output_path = os.path.join(OUTPUT_DIRECTORY, "data")
    os.makedirs(output_path, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)

    # Binance client
    binance_client = BinanceClient(logger)

    # token params
    token0 = "0x4200000000000000000000000000000000000006" # weth
    token1 = "0x078D782b760474a361dDA0AF3839290b0EF57AD6" # usdc
    token0_amounts = [10000000000000, 1000000000000]
    unichain_client = UnichainClient(token0, token1, token0_amounts, logger)

    # start threads
    threads = [
        threading.Thread(target=binance_task, args=(binance_client, output_path, logger, STREAM_DURATION)),
        threading.Thread(target=unichain_task, args=(unichain_client, output_path, logger, STREAM_DURATION)),
    ]
    for t in threads:
        t.start()

    # wait to finish
    for t in threads:
        t.join()

if __name__ == "__main__":
    main()
