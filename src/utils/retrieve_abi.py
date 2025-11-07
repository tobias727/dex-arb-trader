import os
import json
import requests
from src.utils.exceptions import RetrieveAbiError
from src.config import ETHERSCAN_API_KEY, OUTPUT_DIRECTORY
from src.config import validate_eth_address


def save_abi_to_file(contract_address: str, chain_id, logger) -> None:
    """Saves ABI to file given a contract address and chain-ID"""
    contract_address = validate_eth_address(contract_address)
    contract_abi = _get_contract_abi(contract_address, chain_id)
    output_file_path = os.path.join(
        OUTPUT_DIRECTORY, f"abis/{chain_id}_{contract_address}_abi.json"
    )
    with open(output_file_path, "w", encoding="utf-8") as json_file:
        json.dump(contract_abi, json_file, indent=4)
    logger.info(f"ABI saved to: {output_file_path}")


def load_abi(contract_address: str, chain_id: str):
    """Helper function to load abi from file given contract_address and chain_id"""
    try:
        contract_address = validate_eth_address(contract_address)
        file_name = os.path.join(
            OUTPUT_DIRECTORY, f"abis/{chain_id}_{contract_address}_abi.json"
        )
        if not os.path.exists(file_name):
            raise FileNotFoundError(
                f"ABI file not found for contract {contract_address} on chain {chain_id}"
            )
        with open(file_name, "r", encoding="utf-8") as f:
            abi = json.load(f)
        return abi
    except Exception as e:
        raise RetrieveAbiError(
            f"An error occurred while loading ABI for {contract_address}: {e}"
        ) from e


def _get_contract_abi(contract_address: str, chain_id: str) -> dict:
    """Retrieves the ABI of a smart contract from Etherscan given a contract address"""
    etherscan_url = f"https://api.etherscan.io/v2/api?chainid={chain_id}&module=contract&action=getabi&address={contract_address}&apikey={ETHERSCAN_API_KEY}"
    response = requests.get(etherscan_url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if data["status"] == "1":
            contract_abi = json.loads(data["result"])
        else:
            raise RetrieveAbiError(f"Error from Etherscan API: {data['result']}")
    else:
        raise RetrieveAbiError(
            f"Failed to fetch data from Etherscan. HTTP status code: {response.status_code}"
        )
    return contract_abi


def load_abi_if_not_exist(logger, contract_address, chain_id):
    """Method to download ABI if it doesn't exist and return abi"""
    abi_filename = validate_eth_address(contract_address)
    abi_filepath = os.path.join(
        OUTPUT_DIRECTORY, f"abis/{chain_id}_{abi_filename}_abi.json"
    )
    if os.path.exists(abi_filepath):
        logger.info(
            f"✅ ABI already exists, skipping retrieval for {chain_id}_{abi_filename}_abi.json"
        )
    else:
        logger.info("⏳ ABI not found. Loading...")
        save_abi_to_file(contract_address, chain_id, logger)
    return load_abi(contract_address, chain_id)


def load_contract(logger, contract_address, chain_id, web3_connection):
    """Loads contract for a given contract address"""
    abi = load_abi_if_not_exist(logger, contract_address, chain_id)
    address = validate_eth_address(contract_address)
    return web3_connection.eth.contract(address=address, abi=abi)
