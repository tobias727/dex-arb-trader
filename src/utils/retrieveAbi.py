import os
import json
import requests
from web3 import Web3
from src.config import ETHERSCAN_API_KEY, OUTPUT_DIRECTORY


def save_abi_to_file(contract_address: str, chain_id="1") -> None:
    """Saves ABI to file given a contract address
    Optional input: chain_id 1 (mainnet)"""
    try:
        contract_address = _validate_contract_address(contract_address)
        contract_abi = _get_contract_abi(contract_address, chain_id)
        output_file_path = os.path.join(OUTPUT_DIRECTORY, f"abis/{chain_id}_{contract_address}_abi.json")
        with open(output_file_path, "w", encoding="utf-8") as json_file:
            json.dump(contract_abi, json_file, indent=4)
        print(f"ABI saved to: {output_file_path}")
    except Exception as e:
        raise Exception(f"An error occurred during save_abi_to_file: {e}")

def load_abi(contract_address: str, chain_id: str):
    """Helper function to load abi from file given contract_address and chain_id"""
    try:
        file_name = os.path.join(OUTPUT_DIRECTORY, f"abis/{chain_id}_{contract_address}_abi.json")
        if not os.path.exists(file_name):
            raise FileNotFoundError(f"ABI file not found for contract {contract_address} on chain {chain_id}")
        with open(file_name, "r", encoding="utf-8") as f:
            abi = json.load(f)
        return abi
    except Exception as e:
        raise Exception(f"An error occurred while loading ABI for {contract_address}: {e}")

def _get_contract_abi(contract_address: str, chain_id: str) -> dict:
    """Retrieves the ABI of a smart contract from Etherscan given a contract address"""
    etherscan_url = f"https://api.etherscan.io/v2/api?chainid={chain_id}&module=contract&action=getabi&address={contract_address}&apikey={ETHERSCAN_API_KEY}"
    response = requests.get(etherscan_url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if data["status"] == "1":
            contract_abi = json.loads(data["result"])
        else:
            raise Exception(f"Error from Etherscan API: {data['result']}")
    else:
        raise Exception(f"Failed to fetch data from Etherscan. HTTP status code: {response.status_code}")
    return contract_abi

def _validate_contract_address(address: str) -> str:
    """Validates and converts an Ethereum address to checksum format"""
    if not Web3.is_address(address):
        raise ValueError(f"Invalid Ethereum address provided: {address}")
    return Web3.to_checksum_address(address)
