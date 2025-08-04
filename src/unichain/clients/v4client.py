from src.unichain.helpers.uniswap_v4_helper import get_amounts_out, get_amounts_in
from src.utils.retrieve_abi import load_contract
from src.unichain.clients.params import V4Params
from src.unichain.clients.base_client import BaseUnichainClient
from src.config import (
    UNICHAIN_UNISWAP_V4_QUOTER,
    CHAINID_UNICHAIN,
)


class UnichainV4Client(BaseUnichainClient):
    """Stream data from Unichain"""

    def __init__(self, uniswap_v4_params: V4Params, logger):
        super().__init__(logger)
        # swap params
        self.uniswap_v4_params = uniswap_v4_params
        # load contracts
        self.uniswap_v4_quoter_contract = load_contract(
            self.logger, UNICHAIN_UNISWAP_V4_QUOTER, CHAINID_UNICHAIN, self.web3
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
        for token0_amount in self.uniswap_v4_params.amounts_in:
            token1_amount_out = get_amounts_out(
                self.uniswap_v4_quoter_contract,
                self.uniswap_v4_params.token_in,
                self.uniswap_v4_params.token_out,
                token0_amount,
                self.uniswap_v4_params.pool_fee,
                self.uniswap_v4_params.pool_tick_spacing,
            )
            token1_amount_in = get_amounts_in(
                self.uniswap_v4_quoter_contract,
                self.uniswap_v4_params.token_in,
                self.uniswap_v4_params.token_out,
                token0_amount,
                self.uniswap_v4_params.pool_fee,
                self.uniswap_v4_params.pool_tick_spacing,
            )
            token1_amounts_out.append(token1_amount_out)
            token1_amounts_in.append(token1_amount_in)
        return {
            "token0_amounts": self.uniswap_v4_params.amounts_in,
            "token1_outputs": token1_amounts_out,
            "token1_inputs": token1_amounts_in,
        }
