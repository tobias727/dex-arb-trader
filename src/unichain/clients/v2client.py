from typing import List
from src.unichain.helpers.uniswap_v2_helper import get_amounts_out, get_amounts_in
from src.utils.retrieve_abi import load_contract
from src.unichain.clients.base_client import BaseUnichainClient
from src.config import (
    UNICHAIN_UNISWAP_V2_ROUTER_02,
    CHAINID_UNICHAIN,
)


class UnichainV2Client(BaseUnichainClient):
    """Stream data from Unichain"""

    def __init__(
        self,
        token0: str,
        token1: str,
        token0_amounts: List[float],
        logger,
    ):
        super().__init__(logger)
        # swap params
        self.token0 = token0
        self.token1 = token1
        self.token0_amounts = token0_amounts
        # load contracts
        self.uniswap_v2_router_contract = load_contract(
            self.logger, UNICHAIN_UNISWAP_V2_ROUTER_02, CHAINID_UNICHAIN, self.web3
        )

    def _get_swap_rates(self):
        """
        Returns bidirectional rates for swapping token pair,
        given amount of token0 (token0_amounts):
        token0->token1 (token1_output),
        token1->token0 (token1_input)
        """
        token1_amounts_out = []
        token1_amounts_in = []
        for token0_amount in self.token0_amounts:
            token1_amount_out = get_amounts_out(
                self.uniswap_v2_router_contract,
                self.token0,
                self.token1,
                token0_amount,
            )
            token1_amount_in = get_amounts_in(
                self.uniswap_v2_router_contract,
                self.token1,
                self.token0,
                token0_amount,
            )
            token1_amounts_out.append(token1_amount_out)
            token1_amounts_in.append(token1_amount_in)
        return {
            "token0_amounts": self.token0_amounts,
            "token1_outputs": token1_amounts_out,
            "token1_inputs": token1_amounts_in,
        }
