import csv
import os
import time
from typing import Dict, List

from web3 import Web3
from v2_client import UniswapV2Client
from src.config import (
    OUTPUT_DIRECTORY,
    UNICHAIN_WETH,
    UNICHAIN_USDC,
    ALCHEMY_UNICHAIN_BASE_RPC_URL,
    ALCHEMY_API_KEY,
)

DECIMALS_USDC: int = 6 # https://uniscan.xyz/token/0x078D782b760474a361dDA0AF3839290b0EF57AD6
DECIMALS_WETH: int = 18 # https://uniscan.xyz/token/0x4200000000000000000000000000000000000006
WETH_INPUT_VALUES: List[float] = [0.0001, 0.001, 0.01] # for comparing market impacts
OUTPUT_CSV_PATH = os.path.join(OUTPUT_DIRECTORY, "data", "block_data.csv")


def init_web3() -> Web3:
    """Create a Web3 instance connected to Alchemy's Unichain endpoint."""
    rpc_url = f"{ALCHEMY_UNICHAIN_BASE_RPC_URL}{ALCHEMY_API_KEY}"
    web3 = Web3(Web3.HTTPProvider(rpc_url))

    if not web3.is_connected():
        raise ConnectionError("Could not establish a connection with Alchemy RPC")

    print("Connected to Unichain network.")
    return web3

def get_block_and_swap_data(
    web3: Web3,
    client: UniswapV2Client,
    block: Dict,
    input_values: List[float],
) -> Dict:
    """
    Extract timestamp from a block and compute `getAmountsOut` for the
    supplied input values.
    """
    timestamp = web3.to_int(block["timestamp"])
    output_values: List[str] = []

    for amount_in in input_values:
        quote = client.get_amounts_out(
            token_in=UNICHAIN_WETH,
            token_out=UNICHAIN_USDC,
            amount_in=amount_in,
            decimals_in=DECIMALS_WETH,
            decimals_out=DECIMALS_USDC,
        )
        output_values.append(quote["forward"])

    return {
        "timestamp": timestamp,
        "input_values": input_values,
        "output_values": output_values,
    }

def save_to_csv(rows: List[Dict], csv_path: str) -> None:
    """Persist collected data onto disk."""
    if not rows:
        print("No data to save.")
        return

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    with open(csv_path, mode="w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "input_value", "output_value"])

        for entry in rows:
            ts = entry["timestamp"]
            for inp, out in zip(entry["input_values"], entry["output_values"]):
                writer.writerow([ts, inp, out])

    print(f"Data successfully saved to {csv_path}.")

def stream_blocks(
    web3: Web3,
    client: UniswapV2Client,
    input_values: List[float],
    csv_path: str,
) -> None:
    """
    Poll new blocks and collect swap quotes until interrupted (Ctrl-C).
    """
    collected_rows: List[Dict] = []

    try:
        print("Listening for new blocks...")
        current_block = web3.eth.get_block("latest")["number"]

        while True:
            latest_block = web3.eth.get_block("latest")

            # New block?
            if latest_block["number"] > current_block:
                print(f"New block detected: {latest_block['number']}")
                data = get_block_and_swap_data(web3, client, latest_block, input_values)
                collected_rows.append(data)
                print(f"Block {latest_block['number']} processed: {data}")

                current_block = latest_block["number"]

            time.sleep(0.3)  # throttle
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received, saving data…")
        save_to_csv(collected_rows, csv_path)
    except Exception as exc:
        print(f"Unexpected error: {exc}")

def main() -> None:
    """Main entry point"""
    web3 = init_web3()
    uniswap_client = UniswapV2Client()

    stream_blocks(
        web3=web3,
        client=uniswap_client,
        input_values=WETH_INPUT_VALUES,
        csv_path=OUTPUT_CSV_PATH,
    )

if __name__ == "__main__":
    main()
