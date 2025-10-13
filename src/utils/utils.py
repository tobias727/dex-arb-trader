import time
from decimal import Decimal
import requests
from src.utils.types import NotionalValues, InputAmounts
from src.config import (
    TOKEN1_DECIMALS,
    TOKEN0_INPUT,
    BINANCE_MIN_QTY,
    BINANCE_STEP_SIZE,
    BINANCE_MIN_NOTIONAL,
    GAS_RESERVE,
)
from src.utils.exceptions import InsufficientBalanceError, IPChangeError


def elapsed_ms(start_time: float) -> str:
    """Return elapsed time since start in ms, formatted in brackets."""
    return f"[ET { (time.perf_counter() - start_time) * 1000:.1f} ms]"


def get_public_ip():
    """Returns IP-Address to monitor for binance allowlist"""
    try:
        return requests.get("https://api.ipify.org", timeout=3).text
    except Exception as e:
        raise IPChangeError("Failed to retrieve initial public IP.") from e


def check_ip_change(initial_ip, last_ip_check_time):
    """Check if the IP address changed (last 5 minutes)"""
    current_time = time.time()
    if current_time - last_ip_check_time >= 300:  # 5 minutes
        current_ip = get_public_ip()
        if current_ip != initial_ip:
            raise IPChangeError(
                f"Public IP changed from {initial_ip} to {current_ip}. Aborting for security."
            )
        last_ip_check_time = current_time
    return last_ip_check_time


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


def calculate_input_amounts(balances, current_price) -> InputAmounts:
    """Function to determine input amounts"""

    def _quantize_step_size(amount, step_size) -> float:
        """Returns amount rounded down to nearest multiple of step_size"""
        step = Decimal(str(step_size))
        amt = Decimal(str(amount))
        return float((amt // step) * step)

    eth_binance = float(balances["binance"]["ETH"])
    usdc_binance = float(balances["binance"]["USDC"])

    eth_uniswap = balances["uniswap"]["ETH"]
    usdc_uniswap = balances["uniswap"]["USDC"]

    # Binance Buy
    order_value = TOKEN0_INPUT * current_price
    binance_buy = None
    if BINANCE_MIN_NOTIONAL <= order_value <= usdc_binance:
        binance_buy = _quantize_step_size(TOKEN0_INPUT, BINANCE_STEP_SIZE)

    # Binance Sell
    available = _quantize_step_size(eth_binance, BINANCE_STEP_SIZE)
    sell_value = available * current_price
    binance_sell = None
    if available >= BINANCE_MIN_QTY and sell_value >= BINANCE_MIN_NOTIONAL:
        binance_sell = available

    # Uniswap Buy
    uniswap_buy = usdc_uniswap if usdc_uniswap > 0 else None

    # Uniswap Sell
    expected_cost = TOKEN0_INPUT + GAS_RESERVE
    uniswap_sell = TOKEN0_INPUT if eth_uniswap >= expected_cost else None

    if binance_buy is None or uniswap_sell is None:
        binance_buy = None
        uniswap_sell = None

    if binance_sell is None or uniswap_buy is None:
        binance_sell = None
        uniswap_buy = None

    return InputAmounts(
        binance_buy,
        binance_sell,
        uniswap_buy,
        uniswap_sell,
    )
