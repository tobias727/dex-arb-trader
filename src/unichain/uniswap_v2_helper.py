import os
from web3 import Web3
from src.utils.retrieveAbi import save_abi_to_file, load_abi, validate_contract_address
from src.config import (
    CHAINID_UNICHAIN,
    UNICHAIN_UNISWAP_V2_ROUTER_02,
    OUTPUT_DIRECTORY,
)


def load_abi_if_not_exist(logger):
    """Method to download ABI if it doesn't exist and return abi"""
    abi_filename = validate_contract_address(UNICHAIN_UNISWAP_V2_ROUTER_02)
    abi_filepath = os.path.join(
        OUTPUT_DIRECTORY, f"abis/{CHAINID_UNICHAIN}_{abi_filename}_abi.json"
    )
    if os.path.exists(abi_filepath):
        logger.info(
            f"✅ ABI already exists, skipping retrieval for {CHAINID_UNICHAIN}_{abi_filename}_abi.json"
        )
    else:
        logger.info("⏳ ABI not found. Loading...")
        save_abi_to_file(UNICHAIN_UNISWAP_V2_ROUTER_02, CHAINID_UNICHAIN, logger)
    return load_abi(UNICHAIN_UNISWAP_V2_ROUTER_02, CHAINID_UNICHAIN)


def get_amounts_out(
    router_contract,
    token_in: str,
    token_out: str,
    amount_in: float,
) -> dict:
    """
    Calls getAmountsOut for a given token pair and input amount.
    Given an input amount of an asset and pair reserves, returns
    the maximum output amount of the other asset.
    """
    try:
        amount_out = router_contract.functions.getAmountsOut(
            int(amount_in),
            [Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out)],
        ).call()[-1]
        return amount_out
    except Exception as e:
        print(f"Error in get_amounts_out: {e}")
        return None


def get_amounts_in(
    router_contract,
    token_in: str,
    token_out: str,
    amount_out: float,
) -> dict:
    """
    Calls getAmountsIn for a given token pair and input amount.
    Given an output amount of an asset and pair reserves, returns
    a required input amount of the other asset
    """
    try:
        amount_in = router_contract.functions.getAmountsIn(
            int(amount_out),
            [Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out)],
        ).call()[0]
        return amount_in
    except Exception as e:
        print(f"Error in get_amounts_in: {e}")
        return amount_in
