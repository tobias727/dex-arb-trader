import os
from web3 import Web3


def get_amounts_out(
    v4_quoter_contract,
    token_in: str,
    token_out: str,
    amount_in: float,
    pool_fee: int,
    pool_tick_spacing: int,
    pool_hooks: str = "0x0000000000000000000000000000000000000000",
):
    """
    Calls quoteExactInputSingle using V4Quoter
    Returns (amount_out, gas)
    """
    try:
        pool_key = (
            Web3.to_checksum_address(token_in),  # currency0
            Web3.to_checksum_address(token_out),  # currency1
            pool_fee,  # fee (uint24)
            pool_tick_spacing,  # tickSpacing (int24)
            Web3.to_checksum_address(pool_hooks),
        )

        quote_input_params = (
            pool_key,
            True,  # zeroForOne (bool)
            amount_in,  # exactAmount (uint128)
            b"",  # hookData (bytes)
        )

        return v4_quoter_contract.functions.quoteExactInputSingle(
            quote_input_params
        ).call()
    except Exception as e:
        print(f"Error in get_amounts_out: {e}")
        return None


def get_amounts_in(
    v4_quoter_contract,
    token_in: str,
    token_out: str,
    amount_out: float,
    pool_fee: int,
    pool_tick_spacing: int,
    pool_hooks: str = "0x0000000000000000000000000000000000000000",
):
    """
    Calls quoteExactOutputSingle using V4Quoter
    Returns (amount_in, gas)
    """
    try:
        pool_key = (
            Web3.to_checksum_address(token_in),  # currency0
            Web3.to_checksum_address(token_out),  # currency1
            pool_fee,  # fee (uint24)
            pool_tick_spacing,  # tickSpacing (int24)
            Web3.to_checksum_address(pool_hooks),
        )

        quote_output_params = (
            pool_key,
            False,  # zeroForOne (bool)
            amount_out,  # exactAmount (uint128)
            b"",  # hookData (bytes)
        )

        return v4_quoter_contract.functions.quoteExactOutputSingle(
            quote_output_params
        ).call()
    except Exception as e:
        print(f"Error in get_amounts_out: {e}")
        return None
