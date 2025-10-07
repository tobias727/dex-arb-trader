import time
import requests
from src.utils.types import NotionalValues
from src.config import (
    TOKEN1_DECIMALS,
    TOKEN0_INPUT,
)
from src.utils.exceptions import InsufficientBalanceError


def elapsed_ms(start_time: float) -> str:
    """Return elapsed time since start in ms, formatted in brackets."""
    return f"[ET { (time.perf_counter() - start_time) * 1000:.1f} ms]"


def get_public_ip():
    """Returns IP-Address to monitor for binance allowlist"""
    try:
        return requests.get("https://api.ipify.org", timeout=3).text
    except Exception:
        raise Exception("Failed to retrieve initial public IP.")


def check_pre_trade(
    logger,
    balances: dict,
    b_side: str,
    u_side: str,
    notional: NotionalValues,
    buffer: float = 1.01,
):
    """only continue  if balances are sufficient"""
    required = {
        "binance": {
            "BUY": notional.b_ask * buffer / 10**TOKEN1_DECIMALS,  # need USDC
            "SELL": TOKEN0_INPUT,  # need ETH
        },
        "uniswap": {
            "BUY": notional.u_ask * buffer / 10**TOKEN1_DECIMALS,  # need USDC
            "SELL": TOKEN0_INPUT,  # need ETH
        },
    }
    token_map = {"BUY": "USDC", "SELL": "ETH"}

    # Binance check
    needed_token = token_map[b_side]
    if float(balances["binance"][needed_token]) < required["binance"][b_side]:
        message = (
            f"Binance {needed_token} insufficient: "
            f"Required: {required['binance'][b_side]}, "
            f"Available: {balances['binance'][needed_token]}"
        )
        logger.error(message)
        raise InsufficientBalanceError(message)

    # Uniswap check
    needed_token = token_map[u_side]
    if float(balances["uniswap"][needed_token]) < required["uniswap"][u_side]:
        message = (
            f"Uniswap {needed_token} insufficient: "
            f"Required: {required['uniswap'][u_side]}, "
            f"Available: {balances['uniswap'][needed_token]}"
        )
        logger.error(message)
        raise InsufficientBalanceError(message)
