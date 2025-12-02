import json
import asyncio
import aiohttp
from web3 import Web3
from eth_abi import encode
from eth_abi.packed import encode_packed
from src.config import (
    TESTNET,
    TOKEN0_INPUT,
    UNICHAIN_UNISWAP_V4_QUOTER,
    UNICHAIN_SEPOLIA_UNISWAP_V4_QUOTER,
    UNICHAIN_CHAINID,
    UNICHAIN_SEPOLIA_CHAINID,
    TOKEN0_DECIMALS,
    PRIVATE_KEY,
    PRIVATE_KEY_TESTNET,
    WALLET_ADDRESS,
    WALLET_ADDRESS_TESTNET,
    UNICHAIN_UNIVERSAL_ROUTER_ADDRESS,
    UNICHAIN_SEPOLIA_UNIVERSAL_ROUTER_ADDRESS,
    UNICHAIN_ETH_NATIVE,
    UNICHAIN_USDC,
    UNICHAIN_SEPOLIA_USDC,
    UNICHAIN_RPC_URL,
    ALCHEMY_API_KEY,
    UNICHAIN_SEPOLIA_RPC_URL,
    UNICHAIN_SEPOLIA_WS_URL,
    UNICHAIN_WS_URL,
    UNIVERSAL_ROUTER_ABI,
    V4_QUOTER_ABI,
    UNICHAIN_SEPOLIA_FLASHBLOCKS_WS_URL,
    UNICHAIN_FLASHBLOCKS_WS_URL,
    UNICHAIN_SEQUENCER_RPC_URL,
    UNICHAIN_SEPOLIA_SEQUENCER_RPC_URL,
)


# pylint: disable=too-many-instance-attributes, too-few-public-methods
class State:
    """Runtime state container for UniswapV4Client."""

    def __init__(self):
        base_ws_url = UNICHAIN_SEPOLIA_WS_URL if TESTNET else UNICHAIN_WS_URL
        base_rpc_url = UNICHAIN_SEPOLIA_RPC_URL if TESTNET else UNICHAIN_RPC_URL
        api_key = ALCHEMY_API_KEY
        self.url_ws = f"{base_ws_url}{api_key}" if api_key else base_ws_url
        self.url_rpc = f"{base_rpc_url}{api_key}" if api_key else base_rpc_url
        self.sequencer_rpc_url = (
            UNICHAIN_SEPOLIA_SEQUENCER_RPC_URL
            if TESTNET
            else UNICHAIN_SEQUENCER_RPC_URL
        )
        self.flashblock_ws = (
            UNICHAIN_SEPOLIA_FLASHBLOCKS_WS_URL
            if TESTNET
            else UNICHAIN_FLASHBLOCKS_WS_URL
        )
        self.web3_sequencer_rpc = Web3(Web3.HTTPProvider(self.sequencer_rpc_url))
        self.web3_rpc = Web3(Web3.HTTPProvider(self.url_rpc))
        self.wallet_address = WALLET_ADDRESS_TESTNET if TESTNET else WALLET_ADDRESS
        self.private_key = PRIVATE_KEY_TESTNET if TESTNET else PRIVATE_KEY
        self.chain_id = UNICHAIN_SEPOLIA_CHAINID if TESTNET else UNICHAIN_CHAINID
        self.universal_router_address = (
            UNICHAIN_SEPOLIA_UNIVERSAL_ROUTER_ADDRESS
            if TESTNET
            else UNICHAIN_UNIVERSAL_ROUTER_ADDRESS
        )
        self.v4_quoter_address = (
            UNICHAIN_SEPOLIA_UNISWAP_V4_QUOTER
            if TESTNET
            else UNICHAIN_UNISWAP_V4_QUOTER
        )
        self.eth_native_address = UNICHAIN_ETH_NATIVE
        self.usdc_address = UNICHAIN_SEPOLIA_USDC if TESTNET else UNICHAIN_USDC


class UniswapV4Client:
    """DEX client"""

    def __init__(self, logger):
        self.logger = logger
        self.state = State()
        self.session = None
        # router contract
        self.universal_router_contract = self.state.web3_rpc.eth.contract(
            address=self.state.universal_router_address, abi=UNIVERSAL_ROUTER_ABI
        )
        # v4 quoter contract
        self.v4_quoter_contract = self.state.web3_rpc.eth.contract(
            address=self.state.v4_quoter_address, abi=V4_QUOTER_ABI
        )
        if not TESTNET:
            self._check_web3_connection()
        self.calldata_get_amounts_out = self.encode_get_amounts_out()
        self.calldata_get_amounts_in = self.encode_get_amounts_in()

    async def init_session(self):
        """Opens connection"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Closes connection"""
        if self.session:
            await self.session.close()

    @staticmethod
    async def decode_uniswap_quote(response_hex):
        """Returns amount, gas"""
        v1 = int(response_hex[2:66], 16)
        v2 = int(response_hex[66:130], 16)
        return v1, v2

    async def execute_trade(self, zero_for_one, cap_token1, current_block_number):
        """Sends send_bundle to sequencer with slippage protection"""
        bundle_params = {
            "txs": [
                "0x" + self.encode_and_sign_exec_tx(zero_for_one, cap_token1).hex()
            ],
            "minBlockNumber": hex(current_block_number + 1),
            "maxBlockNumber": hex(current_block_number + 3),
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_sendBundle",
            "params": [bundle_params],
        }
        print(json.dumps(payload, indent=2))
        async with self.session.post(
            self.state.sequencer_rpc_url, json=payload, timeout=5
        ) as r:
            r.raise_for_status()
            data = await r.json()
        if "error" in data:
            code = data["error"].get("code")
            message = data["error"].get("message")
            if code == -32602:
                raise ValueError(f"Bundle rejected: {message}")
        bundle_hash = data["result"]["bundleHash"]
        receipt = await self.wait_for_bundle_receipt(bundle_hash)
        return receipt

    async def wait_for_bundle_receipt(self, bundle_hash, attempts=30, interval=0.2):
        """Custom function to poll for bundle receipt"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_getTransactionReceipt",
            "params": [bundle_hash],
        }
        for _ in range(attempts):
            async with self.session.post(
                self.state.sequencer_rpc_url, json=payload, timeout=5
            ) as r:
                r.raise_for_status()
                data = await r.json()
            if "error" in data:
                code = data["error"].get("code")
                if code == -32602:
                    self.logger.warning(
                        "Bundle was dropped from the pool (likely expired)"
                    )
                    return None
            receipt = data.get("result")
            if receipt:
                return receipt
            await asyncio.sleep(interval)
        raise TimeoutError("No receipt within polling period")

    async def on_new_block(self, ws):
        """Sends RFQ via ws"""
        # amounts out
        sim_req_out = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "eth_call",
            "params": [
                {
                    "to": self.state.v4_quoter_address,
                    "data": self.calldata_get_amounts_out,
                },
                "pending",
            ],
        }
        # amounts in
        sim_req_in = {
            "jsonrpc": "2.0",
            "id": 43,
            "method": "eth_call",
            "params": [
                {
                    "to": self.state.v4_quoter_address,
                    "data": self.calldata_get_amounts_in,
                },
                "pending",
            ],
        }
        await ws.send(json.dumps(sim_req_out))
        await ws.send(json.dumps(sim_req_in))

    def encode_get_amounts_out(self):
        """Returns calldata for Bid"""
        pool_key = (
            self.state.eth_native_address,
            self.state.usdc_address,
            500,
            10,
            "0x0000000000000000000000000000000000000000",
        )
        quote_input_params = (
            pool_key,
            True,
            int(TOKEN0_INPUT * 10**TOKEN0_DECIMALS),
            b"",
        )
        return self.v4_quoter_contract.encode_abi(
            "quoteExactInputSingle", args=[quote_input_params]
        )

    def encode_get_amounts_in(self):
        """Returns calldata for Ask"""
        pool_key = (
            self.state.eth_native_address,
            self.state.usdc_address,
            500,
            10,
            "0x0000000000000000000000000000000000000000",
        )
        quote_input_params = (
            pool_key,
            False,
            int(TOKEN0_INPUT * 10**TOKEN0_DECIMALS),
            b"",
        )
        return self.v4_quoter_contract.encode_abi(
            "quoteExactOutputSingle", args=[quote_input_params]
        )

    def encode_and_sign_exec_tx(self, zero_for_one: bool, cap_token1: int):
        """zero_for_one: False for BUY, True for SELL"""
        amount_token0 = int(TOKEN0_INPUT * 10**TOKEN0_DECIMALS)
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
                self.state.eth_native_address,  # currency0
                self.state.usdc_address,  # currency1
                500,  # fee (uint24)
                10,  # tickSpacing (int24)
                "0x0000000000000000000000000000000000000000",  # poolHooks
                zero_for_one,  # zeroForOne
                amount_token0,  # amountIn / amountOut
                cap_token1,  # amountOutMinimum / amountInMaximum
                b"",  # hookData
            ],
        )
        settle_all_params = encode(
            ["address", "uint128"],
            [
                (
                    self.state.eth_native_address
                    if zero_for_one
                    else self.state.usdc_address
                ),
                2**128 - 1,
            ],
        )
        take_all_params = encode(
            ["address", "uint128"],
            [
                (
                    self.state.usdc_address
                    if zero_for_one
                    else self.state.eth_native_address
                ),
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
        calldata = self.universal_router_contract.encode_abi(
            "execute", args=[commands, inputs]
        )
        tx = {
            "from": self.state.wallet_address,
            "to": self.state.universal_router_address,
            "data": calldata,
            "value": amount_token0 if zero_for_one else 0,
            "nonce": self.state.web3_rpc.eth.get_transaction_count(
                self.state.wallet_address, "pending"
            ),
            "gas": 1_000_000,
            "maxFeePerGas": 1_100_000_000,
            "type": "0x2",
            "maxPriorityFeePerGas": 1_000_000_000,
            "chainId": self.state.chain_id,
        }
        signed = self.state.web3_rpc.eth.account.sign_transaction(
            tx, self.state.private_key
        )
        return signed.raw_transaction

    async def get_balances(self):
        """Returns balances for USDC and ETH"""
        # eth
        payload_eth = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [self.state.wallet_address, "pending"],
            "id": 101,
        }
        # usdc (erc20)
        payload_usdc = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {
                    "to": self.state.usdc_address,
                    # method-id + address
                    "data": "0x70a08231000000000000000000000000"
                    + self.state.wallet_address[2:],
                },
                "pending",
            ],
            "id": 102,
        }
        tasks = [
            self.session.post(self.state.url_rpc, json=payload_eth),
            self.session.post(self.state.url_rpc, json=payload_usdc),
        ]
        resp_eth, resp_usdc = await asyncio.gather(*tasks)
        result_eth = await resp_eth.json()
        result_usdc = await resp_usdc.json()

        balance_eth = int(result_eth["result"], 16) / 1e18  # ETH → float
        balance_usdc = int(result_usdc["result"], 16) / 1e6  # USDC → float

        return balance_eth, balance_usdc

    async def get_trade_result(self, tx_hash):
        """Returns tx_receipt given tx_hash"""
        return await self.state.web3_rpc.eth.wait_for_transaction_receipt(tx_hash)

    def _check_web3_connection(self):
        if not self.state.web3_rpc.is_connected():
            raise ConnectionError("Could not establish a connection with Alchemy RPC")
