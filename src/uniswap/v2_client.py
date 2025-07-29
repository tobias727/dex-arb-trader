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

    def get_amounts_out(
        self,
        token_in: str,
        token_out: str,
        amount_in: float,
        decimals_in: int,
        decimals_out: int,
    ) -> dict:
        """
        Get the output amounts for a given input token and amount, including both
        directions (token_in -> token_out and token_out -> token_in), and return
        both the raw on-chain values and the human-readable values.

        Parameters
        ----------
        token_in : str
            Address of the input token.
        token_out : str
            Address of the output token.
        amount_in : float
            Input amount (human-readable, e.g. 0.01 WETH).
        decimals_in : int
            Decimals of the input token.
        decimals_out : int
            Decimals of the output token.

        Returns
        -------
        dict
            {
                "forward_raw":   <int>,   # raw wei amount (token_in → token_out)
                "forward":       <float>, # human-readable using decimals_out
                "reverse_raw":   <int>,   # raw wei amount (token_out → token_in)
                "reverse":       <float>, # human-readable using decimals_in
            }
        """
        try:
            # Convert the human-readable input amount to wei
            amount_in_wei = int(amount_in * (10 ** decimals_in))

            # Forward direction: token_in -> token_out
            forward_raw = self.router_contract.functions.getAmountsOut(
                amount_in_wei,
                [
                    Web3.to_checksum_address(token_in),
                    Web3.to_checksum_address(token_out),
                ],
            ).call()[-1]

            # Reverse direction: token_out -> token_in
            reverse_raw = self.router_contract.functions.getAmountsOut(
                amount_in_wei,
                [
                    Web3.to_checksum_address(token_out),
                    Web3.to_checksum_address(token_in),
                ],
            ).call()[-1]

            # Convert raw values to human-readable amounts
            forward_human = forward_raw / (10 ** decimals_out)
            reverse_human = reverse_raw / (10 ** decimals_in)

            return {
                "forward_raw": forward_raw,
                "forward": forward_human,
                "reverse_raw": reverse_raw,
                "reverse": reverse_human,
            }

        except Exception as e:
            print(f"Error fetching amounts out: {e}")
            return {
                "forward_raw": None,
                "forward": None,
                "reverse_raw": None,
                "reverse": None,
            }
