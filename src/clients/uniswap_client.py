import asyncio
import time
from web3.contract.contract import Contract
from web3.types import TxReceipt
from eth_account.types import TransactionDictType
from eth_abi import encode
from eth_abi.packed import encode_packed


from utils.web3_utils import connect_web3, connect_web3_async
from config import (
    ERC20_ABI,
    TOKEN0_INPUT,
    UNICHAIN_CHAINID,
    TOKEN0_DECIMALS,
    PRIVATE_KEY,
    WALLET_ADDRESS,
    UNICHAIN_UNIVERSAL_ROUTER_ADDRESS,
    UNICHAIN_ETH_NATIVE,
    UNICHAIN_USDC,
    UNICHAIN_RPC_URL,
    ALCHEMY_API_KEY,
    UNIVERSAL_ROUTER_ABI,
    UNICHAIN_SEQUENCER_RPC_URL,
)


class UniswapClient:
    """DEX client"""

    __slots__ = (
        "w3_seq",
        "nonce",
        "account",
        "universal_router_contract",
    )

    def __init__(self):
        # sequencer session
        self.w3_seq = connect_web3_async(UNICHAIN_SEQUENCER_RPC_URL)
        # nonce, account
        w3 = connect_web3(UNICHAIN_RPC_URL + ALCHEMY_API_KEY)
        self.nonce = w3.eth.get_transaction_count(WALLET_ADDRESS, "pending")
        self.account = w3.eth.account
        # router contract
        self.universal_router_contract = w3.eth.contract(
            address=UNICHAIN_UNIVERSAL_ROUTER_ADDRESS, abi=UNIVERSAL_ROUTER_ABI
        )

    async def keep_connection_hot(self, ping_interval: int = 30) -> None:
        """Sends HTTP request to keep TCP/TLS connection alive"""
        while True:
            # TODO: implement
            await asyncio.sleep(ping_interval)

    async def execute_trade(
        self, zero_for_one: bool, amount_token0: float
    ) -> TxReceipt:
        """Builds and broadcasts tx"""
        tx = self.build_tx(
            zero_for_one, self.universal_router_contract, self.nonce, amount_token0
        )
        signed_tx = self.account.sign_transaction(tx, PRIVATE_KEY)  # bottleneck: 4-8 ms
        tx_hash = await self.w3_seq.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await self.w3_seq.eth.wait_for_transaction_receipt(tx_hash)

        # increase nonce
        self.nonce += 1
        assert receipt
        return receipt

    @staticmethod
    def get_balances() -> tuple[float, float]:
        """Returns balances for USDC and ETH"""
        w3 = connect_web3(UNICHAIN_RPC_URL + ALCHEMY_API_KEY)
        wei_eth = w3.eth.get_balance(WALLET_ADDRESS, "pending")
        balance_eth = wei_eth / 1e18
        usdc = w3.eth.contract(address=UNICHAIN_USDC, abi=ERC20_ABI)
        raw_usdc = usdc.functions.balanceOf(WALLET_ADDRESS).call(
            block_identifier="pending"
        )
        balance_usdc = raw_usdc / 1e6
        return balance_eth, balance_usdc  # float, float

    @staticmethod
    def build_tx(
        zero_for_one: bool,
        universal_router_contract: Contract,
        nonce: int,
        amount_token0: float,
    ) -> TransactionDictType:
        """zero_for_one: False for BUY, True for SELL"""
        amount_token0 = int(amount_token0 * 10**TOKEN0_DECIMALS)
        swap_exact_params = encode(
            [
                "address",
                "address",
                "uint24",
                "int24",
                "address",
                "bool",
                "uint128",
                "uint128",
                "bytes",
            ],
            [
                UNICHAIN_ETH_NATIVE,  # currency0
                UNICHAIN_USDC,  # currency1
                500,  # fee (uint24)
                10,  # tickSpacing (int24)
                "0x0000000000000000000000000000000000000000",  # poolHooks
                zero_for_one,  # zeroForOne
                amount_token0,  # amountIn / amountOut
                0 if zero_for_one else 2**128 - 1,  # amountOutMinimum / amountInMaximum
                b"",  # hookData
            ],
        )
        settle_all_params = encode(
            ["address", "uint128"],
            [
                (UNICHAIN_ETH_NATIVE if zero_for_one else UNICHAIN_USDC),
                2**128 - 1,
            ],
        )
        take_all_params = encode(
            ["address", "uint128"],
            [
                (UNICHAIN_USDC if zero_for_one else UNICHAIN_ETH_NATIVE),
                0,
            ],
        )
        # 0x06=SWAP_EXACT_IN_SINGLE, 0x08=SWAP_EXACT_OUT_SINGLE
        # 0x0C=SETTLE_ALL
        # 0x0F=TAKE_ALL
        actions = encode_packed(
            ["uint8", "uint8", "uint8"], [0x06 if zero_for_one else 0x08, 0x0C, 0x0F]
        )
        inputs = [
            encode(
                ["bytes", "bytes[]"],
                [actions, [swap_exact_params, settle_all_params, take_all_params]],
            )
        ]
        commands = encode_packed(["uint8"], [0x10])
        calldata = universal_router_contract.encode_abi(
            "execute", args=[commands, inputs]
        )
        return {
            "from": WALLET_ADDRESS,
            "to": UNICHAIN_UNIVERSAL_ROUTER_ADDRESS,
            "data": calldata,
            "value": amount_token0 if zero_for_one else 0,
            "nonce": nonce,
            "gas": 200_000, # ~100-130k gas per tx
            "maxFeePerGas": 101_000, # 258 baseFeePerGas at 2026-01-04
            "type": "0x2",
            "maxPriorityFeePerGas": 100_000,
            "chainId": UNICHAIN_CHAINID,
        }
