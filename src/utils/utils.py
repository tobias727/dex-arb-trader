import time
import json
import csv
import os
from decimal import Decimal, ROUND_DOWN
import requests
from src.utils.types import NotionalValues, InputAmounts
from src.config import (
    TOKEN1_DECIMALS,
    TOKEN0_INPUT,
    GAS_RESERVE,
)
from src.utils.exceptions import InsufficientBalanceError, IPChangeError


def load_pools(json_filepath):
    """Load pool data from json (The Graph)"""
    with open(json_filepath, "r", encoding="utf-8") as f:
        return json.load(f)["data"]["pools"]


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
    eth_binance = float(balances["binance"]["ETH"])
    usdc_binance = float(balances["binance"]["USDC"])

    eth_uniswap = balances["uniswap"]["ETH"]
    usdc_uniswap = balances["uniswap"]["USDC"]

    # CEX_buy_DEX_sell
    if usdc_binance > TOKEN0_INPUT * current_price and eth_uniswap > (
        TOKEN0_INPUT + GAS_RESERVE
    ):
        binance_buy = TOKEN0_INPUT
        uniswap_sell = TOKEN0_INPUT
    else:
        binance_buy = None
        uniswap_sell = None

    # CEX_sell_DEX_buy
    if eth_binance > TOKEN0_INPUT and usdc_uniswap > (TOKEN0_INPUT * current_price):
        binance_sell = TOKEN0_INPUT
        uniswap_buy = TOKEN0_INPUT
    else:
        binance_sell = None
        uniswap_buy = None

    return InputAmounts(
        binance_buy,
        binance_sell,
        uniswap_buy,
        uniswap_sell,
    )


def calculate_pnl(response_binance, receipt_uniswap):
    """Function to calculate PnL after execution"""
    # Here we use binance as price for gas fee calculation in USDC for simplicity
    eth_to_usdc_price = Decimal(response_binance["fills"][0]["price"])
    # uniswap
    uniswap_usdc_amount = Decimal("0")
    for log in receipt_uniswap["logs"]:
        if (
            log["topics"][0].hex()
            == "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
        ):  # Transfer(address,address,uint256)
            uniswap_usdc_amount += Decimal(int(log["data"].hex(), 16)) / Decimal(
                "1000000"
            )  # USDC 6 decimals
    gas_fee_eth = (
        Decimal(receipt_uniswap["gasUsed"])
        * Decimal(receipt_uniswap["effectiveGasPrice"])
        / Decimal(1e18)
    )
    gas_fee_usdc = gas_fee_eth * Decimal(eth_to_usdc_price)

    # binance
    binance_pnl = Decimal("0")
    if response_binance["side"] == "BUY":
        for fill in response_binance["fills"]:
            price = Decimal(fill["price"])
            qty = Decimal(fill["qty"])
            commission = Decimal(fill["commission"])
            # BUY: commission in ETH, convert to USDC
            binance_pnl -= price * qty
            binance_pnl -= commission * price
    elif response_binance["side"] == "SELL":
        for fill in response_binance["fills"]:
            price = Decimal(fill["price"])
            qty = Decimal(fill["qty"])
            commission = Decimal(fill["commission"])
            # SELL: commission in USDC
            binance_pnl += price * qty
            binance_pnl -= commission

    # total
    if response_binance["side"] == "BUY":
        total_pnl = uniswap_usdc_amount + binance_pnl - gas_fee_usdc
    else:  # b_side == "SELL"
        total_pnl = binance_pnl - uniswap_usdc_amount - gas_fee_usdc
    return total_pnl.quantize(Decimal("1e-18"), rounding=ROUND_DOWN)


def append_trade_to_csv(filename, trade_data):
    """Appends trades to csv file in out/, adds current CET timestamp"""
    cet_time = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    trade_data = {"timestamp": cet_time, **trade_data}
    out_path = os.path.join("out", filename)
    os.makedirs("out", exist_ok=True)
    file_exists = os.path.isfile(out_path)
    with open(out_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=trade_data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(trade_data)
