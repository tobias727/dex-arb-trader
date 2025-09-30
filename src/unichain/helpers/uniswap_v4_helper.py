import sys
from web3 import Web3
from requests.exceptions import HTTPError
from src.utils.exceptions import QuoteError


def get_amounts_out(
    logger,
    v4_quoter_contract,
    token_in: str,
    token_out: str,
    amount_token0: int,
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
            int(amount_token0),  # exactAmount (uint128)
            b"",  # hookData (bytes)
        )
        return v4_quoter_contract.functions.quoteExactInputSingle(
            quote_input_params
        ).call()

    except HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            logger.error("❌ UNICHAIN: Rate limit hit (429), stopping bot!")
            sys.exit(1)
        raise QuoteError(f"Unexpected HTTP error in get_amounts_out: {e}") from e

    except Exception as e:
        raise QuoteError(f"Error in get_amounts_out: {e}") from e


def get_amounts_in(
    logger,
    v4_quoter_contract,
    token_in: str,
    token_out: str,
    exact_amount_token0: float,  # token0 as target
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
        return v4_quoter_contract.functions.quoteExactOutputSingle(
            quote_output_params
        ).call()

    except HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            logger.error("❌ UNICHAIN: Rate limit hit (429), stopping bot!")
            sys.exit(1)
        raise QuoteError(f"Unexpected HTTP error in get_amounts_out: {e}") from e

    except Exception as e:
        raise QuoteError(f"Error in get_amounts_out: {e}") from e
