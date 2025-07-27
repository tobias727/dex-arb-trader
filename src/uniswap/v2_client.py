from web3 import Web3
from src.utils.retrieveAbi import save_abi_to_file, load_abi
from src.config import (
    UNICHAIN_UNIVERSAL_ROUTER_V2_ADDRESS,
    CHAINID_UNICHAIN,
    UNICHAIN_UNISWAP_V2_ROUTER_02,
    ALCHEMY_UNICHAIN_BASE_RPC_URL,
    ALCHEMY_API_KEY,
)

class UniswapV2Client:
    """A client for interacting with Uniswap V2 Router on Unichain to retrieve swap estimates"""

    def __init__(self):
        """
        Initialize the UniswapV2Client:
        - Connect to the Web3 provider
        - Check and save/load the router ABI
        - Load the router contract
        """
        alchemy_rpc_url = f"{ALCHEMY_UNICHAIN_BASE_RPC_URL}{ALCHEMY_API_KEY}"
        self.w3 = Web3(Web3.HTTPProvider(alchemy_rpc_url))
        # check connection
        if not self.w3.is_connected():
            raise ConnectionError("Could not establish a connection with Alchemy RPC")
        self.router_address = Web3.to_checksum_address(UNICHAIN_UNISWAP_V2_ROUTER_02)

        # TODO: Check if ABI file exists; if not, save to disk
        save_abi_to_file(UNICHAIN_UNIVERSAL_ROUTER_V2_ADDRESS, chain_id=CHAINID_UNICHAIN)
        save_abi_to_file(self.router_address, chain_id=CHAINID_UNICHAIN)

        # init router contract
        router_abi = load_abi(self.router_address, CHAINID_UNICHAIN)
        if not router_abi:
            raise FileNotFoundError("Failed to load ABI for the Uniswap V2 Router.")
        self.router_contract = self.w3.eth.contract(address=self.router_address, abi=router_abi)

    def get_amounts_out(self, token_in: str, token_out: str, amount_in: float, decimals_in: int) -> dict:
        """
        Get the output amounts for a given input token and amount, including both directions
        (token_in -> token_out and token_out -> token_in).

        Parameters:
        - token_in (str): The input token address.
        - token_out (str): The output token address.
        - amount_in (float): The input amount (in human-readable format, e.g., 0.01 WETH).
        - decimals_in (int): The number of decimals of the input token.

        Returns:
        - dict: Contains the output amount for token_in -> token_out and token_out -> token_in.
        """
        try:
            amount_in_wei = int(amount_in * (10 ** decimals_in)) # uniswap uses wei

            # Forward direction: token_in -> token_out
            amounts_out = self.router_contract.functions.getAmountsOut(
                amount_in_wei, [Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out)]
            ).call()
            output_amount_forward = amounts_out[-1]

            # Reverse direction: token_out -> token_in
            amount_out_wei_reverse = self.router_contract.functions.getAmountsOut(
                amount_in_wei, [Web3.to_checksum_address(token_out), Web3.to_checksum_address(token_in)]
            ).call()
            output_amount_reverse = amount_out_wei_reverse[-1]

            return {
                "forward": output_amount_forward,
                "reverse": output_amount_reverse,
            }

        except Exception as e:
            print(f"Error fetching amounts out: {e}")
            return {"forward": None, "reverse": None}
