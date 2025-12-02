import time
import json
import os
import logging
from decimal import Decimal, ROUND_DOWN
import csv
import asyncio
import aiohttp
from src.config import (
    TESTNET,
    VERSION,
)
from src.utils.exceptions import IPChangeError


def load_pools(json_filepath):
    """Load pool data from json (The Graph)"""
    with open(json_filepath, "r", encoding="utf-8") as f:
        return json.load(f)["data"]["pools"]


async def fetch_public_ip():
    """Returns IP-Address to monitor for binance allowlist"""
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.ipify.org?format=json") as r:
            data = await r.json()
            return data["ip"]


async def monitor_ip_change(logger, interval=300):
    """Check if the IP address changed (last 5 minutes)"""
    initial_ip = await fetch_public_ip()
    logger.info(f"Initial IP: {initial_ip}")
    while True:
        await asyncio.sleep(interval)
        current_ip = await fetch_public_ip()
        if current_ip != initial_ip:
            raise IPChangeError(
                f"Public IP changed: {initial_ip} -> {current_ip}. Aborting for security."
            )


def setup_logger(log_dir: str = "out/logs") -> logging.Logger:
    """Create and configure logger with console + file handlers."""
    log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    os.makedirs(log_dir, exist_ok=True)
    log_file_name = (
        f"trading_bot_v{VERSION}" if TESTNET else f"trading_bot_v{VERSION}_LIVE"
    )
    log_file = os.path.join(log_dir, f"{log_file_name}.log")

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    # File handler
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setFormatter(log_formatter)

    # Logger setup
    logger = logging.getLogger(log_file_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def calculate_pnl(response_binance, receipt_uniswap):
    """Function to calculate PnL after execution"""
    # Here we use binance as price for gas fee calculation in USDC for simplicity
    eth_to_usdc_price = Decimal(response_binance["fills"][0]["price"])
    # uniswap
    uniswap_usdc_amount = Decimal("0")
    for log in receipt_uniswap["logs"]:
        if (
            log["topics"][0].lower()
            == "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
        ):  # Transfer(address,address,uint256)
            uniswap_usdc_amount += Decimal(int(log["data"], 16)) / Decimal(
                "1000000"
            )  # USDC 6 decimals
    gas_fee_eth = (
        Decimal(int(receipt_uniswap["gasUsed"], 16))
        * Decimal(int(receipt_uniswap["effectiveGasPrice"], 16))
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
    return total_pnl.quantize(Decimal("1e-6"), rounding=ROUND_DOWN)


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
