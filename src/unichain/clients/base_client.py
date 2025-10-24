from abc import ABC
from web3 import Web3

from src.config import (
    ALCHEMY_UNICHAIN_BASE_RPC_URL,
    ALCHEMY_UNICHAIN_SEPOLIA_RPC_URL,
    ALCHEMY_API_KEY,
    INFURA_UNICHAIN_BASE_RPC_URL,
    INFURA_API_KEY,
)


class BaseUnichainClient(ABC):
    """Base class for Unichain clients"""

    def __init__(self, logger, testnet: bool = False):
        base_rpc_url = (
            ALCHEMY_UNICHAIN_SEPOLIA_RPC_URL
            if testnet
            else ALCHEMY_UNICHAIN_BASE_RPC_URL
        )
        api_key = "" if testnet else ALCHEMY_API_KEY
        rpc_url = f"{base_rpc_url}{api_key}"
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not testnet:
            self._check_web3_connection()  # for testnet always False
        self.logger = logger
        self.is_streaming = False

    def _check_web3_connection(self):
        if not self.web3.is_connected():
            raise ConnectionError("Could not establish a connection with Alchemy RPC")
