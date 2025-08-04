import os
import threading
import logging
import asyncio
from src.unichain.clients.params import V2Params, V4Params
from src.unichain.clients.base_client import BaseUnichainClient
from src.unichain.clients.v2client import UnichainV2Client
from src.unichain.clients.v4client import UnichainV4Client
from src.binance.client import BinanceClient
from src.config import OUTPUT_DIRECTORY, UNISWAP_PROTOCOL_VERSION, STREAM_DURATION


def binance_task(binance_client: BinanceClient, output_path, logger, duration):
    """Task to handle Binance WebSocket streaming"""
    logger.info("Starting Binance WebSocket stream...")
    asyncio.run(binance_client.ws_stream(duration))
    binance_client.save_to_csv(output_path)
    binance_client.save_to_csv(output_path, latest=True)  # save latest


def unichain_task(unichain_client: BaseUnichainClient, output_path, logger, duration):
    """Task to handle Unichain data streaming"""
    logger.info("Starting Unichain data stream...")
    unichain_client.start_stream(duration)
    unichain_client.save_to_csv(output_path)
    unichain_client.save_to_csv(output_path, latest=True)  # save latest


def main():
    """Main class to stream data"""
    # setup
    output_path = os.path.join(OUTPUT_DIRECTORY, "data")
    os.makedirs(output_path, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)

    # Binance client
    binance_client = BinanceClient(logger)

    # Uniswap client
    if UNISWAP_PROTOCOL_VERSION == "v4":
        uniswap_v4_params = V4Params(
            token_in="0x8f187aa05619a017077f5308904739877ce9ea21",  # eth
            token_out="0x927b51f251480a681271180da4de28d44ec4afb8",  # usdc
            amounts_in=[10**18, 10**17],
            pool_fee=100,
            pool_tick_spacing=1,
        )
        unichain_client = UnichainV4Client(uniswap_v4_params, logger)
    else:
        uniswap_v2_params = V2Params(
            token0 = "0x4200000000000000000000000000000000000006",  # weth # token0,
            token1 = "0x078D782b760474a361dDA0AF3839290b0EF57AD6",  # usdc #token1
            token0_amounts = [10000000000000, 1000000000000],  # token0_amounts
        )
        unichain_client = UnichainV2Client(uniswap_v2_params, logger)

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
