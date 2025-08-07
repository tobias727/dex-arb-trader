import os
import threading
import json
import logging
import asyncio
from src.unichain.clients.base_client import BaseUnichainClient
from src.unichain.clients.v4client import UnichainV4Client
from src.binance.client import BinanceClient
from src.config import OUTPUT_DIRECTORY, UNISWAP_PROTOCOL_VERSION, STREAM_DURATION, LATEST


def binance_task(binance_client: BinanceClient, output_path, logger, duration):
    """Task to handle Binance WebSocket streaming"""
    logger.info("Starting Binance WebSocket stream...")
    asyncio.run(binance_client.run(duration))
    binance_client.save_to_csv(output_path)
    binance_client.save_to_csv(output_path, latest=LATEST)  # save latest


def unichain_task(unichain_client: BaseUnichainClient, output_path, logger, duration):
    """Task to handle Unichain data streaming"""
    logger.info("Starting Unichain data stream...")
    unichain_client.start_stream(output_path, duration, latest=LATEST)


def load_pools(json_filepath):
    """Load pool data from json (The Graph)"""
    with open(json_filepath, "r", encoding="utf-8") as f:
        return json.load(f)["data"]["pools"]


def main():
    """Main class to stream data"""
    # setup
    output_path = os.path.join(OUTPUT_DIRECTORY, "data")
    os.makedirs(output_path, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)

    # Binance client
    binance_client = BinanceClient(logger)

    # Load pools from JSON
    pools_filepath = "unichain_v4_pools.json"
    pools = load_pools(pools_filepath)

    if UNISWAP_PROTOCOL_VERSION == "v4":
        unichain_client = UnichainV4Client(pools, logger)
    else: # v2 is deprecated after commit f04e6907da068ba2bccc4f52555efcebda29d4cf
        raise ValueError("Only Uniswap V4 is supported for this task.")

    # start threads
    threads = [
        threading.Thread(
            target=binance_task,
            args=(binance_client, output_path, logger, STREAM_DURATION),
        ),
        threading.Thread(
            target=unichain_task,
            args=(unichain_client, output_path, logger, STREAM_DURATION),
        ),
    ]
    for t in threads:
        t.start()

    # wait to finish
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
