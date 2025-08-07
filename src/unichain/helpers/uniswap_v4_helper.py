from web3 import Web3


def get_amounts_out(
    v4_quoter_contract,
    token_in: str,
    token_out: str,
    amount_token0: float,
    pool_fee: int,
    pool_tick_spacing: int,
    pool_hooks: str = "0x0000000000000000000000000000000000000000",
):
    """
    How much token1 can we get for amount of token0 ?
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
            amount_token0,  # exactAmount (uint128)
            b"",  # hookData (bytes)
        )
        token_1_amount = v4_quoter_contract.functions.quoteExactInputSingle(
            quote_input_params
        ).call()
        return token_1_amount
    except Exception as e:
        print(f"Error in get_amounts_out: {e}")
        return None


def get_amounts_in(
    v4_quoter_contract,
    token_in: str,
    token_out: str,
    exact_amount_token0: float, # token0 as target
    pool_fee: int,
    pool_tick_spacing: int,
    pool_hooks: str = "0x0000000000000000000000000000000000000000",
):
    """
    How much token1 we have to bid to get exactly token0?
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
            exact_amount_token0,  # exactAmount (uint128)
            b"",  # hookData (bytes)
        )
        token_1_amount = v4_quoter_contract.functions.quoteExactOutputSingle(
            quote_output_params
        ).call()
        return token_1_amount
    except Exception as e:
        print(f"Error in get_amounts_in: {e} +\n\n quote_output_params: {quote_output_params}\n\n")
        return None
