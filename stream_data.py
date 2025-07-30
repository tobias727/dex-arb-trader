import os
import asyncio
import logging
import time
from src.unichain.client import UnichainClient
from src.config import (
    OUTPUT_DIRECTORY
)


async def main():
    """Main class to stream data"""
    # setup
    output_path = os.path.join(OUTPUT_DIRECTORY, "data")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)

    # token params
    token0 = "0x4200000000000000000000000000000000000006" # weth
    token1 = "0x078D782b760474a361dDA0AF3839290b0EF57AD6" # usdc
    token0_amounts = [10000000, 100000000000000000]

    # start stream
    unichain_streamer = UnichainClient(token0, token1, token0_amounts, logger)
    unichain_streamer.start_stream(5)
    unichain_streamer.save_to_csv(output_path)

if __name__ == "__main__":
    asyncio.run(main())
