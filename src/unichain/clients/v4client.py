import asyncio
from web3 import Web3
from eth_abi import encode
from eth_abi.packed import encode_packed
from src.unichain.helpers.uniswap_v4_helper import get_amounts_out, get_amounts_in
from src.utils.retrieve_abi import load_contract
from src.unichain.clients.base_client import BaseUnichainClient
from src.utils.retrieve_abi import (
    load_abi,
    validate_contract_address,
    save_abi_to_file,
    load_abi_if_not_exist,
)
from src.config import (
    UNICHAIN_UNISWAP_V4_QUOTER,
    CHAINID_UNICHAIN,
    CHAINID_UNICHAIN_SEPOLIA_TESTNET,
    ACTIVE_TOKEN0,
    ACTIVE_TOKEN1,
    TOKEN0_INPUT,
    TOKEN0_DECIMALS,
    TOKEN1_DECIMALS,
    PRIVATE_KEY,
    PRIVATE_KEY_TESTNET,
    WALLET_ADDRESS,
    WALLET_ADDRESS_TESTNET,
    COMMAND_V4_SWAP,
    UNICHAIN_SEPOLIA_ROUTER_ADDRESS,
    UNICHAIN_UNIVERSAL_ROUTER_ADDRESS,
    UNICHAIN_ETH_NATIVE,
    UNICHAIN_USDC,
    UNICHAIN_SEPOLIA_USDC,
    ALCHEMY_UNICHAIN_BASE_RPC_URL,
    ALCHEMY_API_KEY,
)


class UnichainV4Client(BaseUnichainClient):
    """Stream data from Unichain"""

    def __init__(self, pools, logger, testnet: bool = False):
        super().__init__(logger, testnet)
        # swap params
        self.pools = pools
        # token_in_amounts is received from get_amounts_in and used during "BUY" side execution to determine input amount
        self.token_in_amount = None
        # load contracts (quoting always from mainnet)
        rpc_url = f"{ALCHEMY_UNICHAIN_BASE_RPC_URL}{ALCHEMY_API_KEY}"
        web3_mainnet = Web3(Web3.HTTPProvider(rpc_url))
        self.uniswap_v4_quoter_contract = load_contract(
            self.logger, UNICHAIN_UNISWAP_V4_QUOTER, CHAINID_UNICHAIN, web3_mainnet
        )
        # init active trading pool
        self.active_trading_pool = next(
            (
                pool
                for pool in self.pools
                if (
                    (
                        pool["token0"]["symbol"] == ACTIVE_TOKEN0
                        and pool["token1"]["symbol"] == ACTIVE_TOKEN1
                    )
                )
            ),
            None,
        )
        # handle values for testnet and mainnet, only for execution
        self.private_key = PRIVATE_KEY_TESTNET if testnet else PRIVATE_KEY
        self.chain_id = (
            CHAINID_UNICHAIN_SEPOLIA_TESTNET if testnet else CHAINID_UNICHAIN
        )
        self.wallet_address = WALLET_ADDRESS_TESTNET if testnet else WALLET_ADDRESS
        self.unichain_eth_native_address = Web3.to_checksum_address(
            UNICHAIN_ETH_NATIVE
        )  # same address for testnet
        self.unichain_usdc_address = Web3.to_checksum_address(
            UNICHAIN_SEPOLIA_USDC if testnet else UNICHAIN_USDC
        )

        # load router contract
        router_address = (
            UNICHAIN_SEPOLIA_ROUTER_ADDRESS
            if testnet
            else UNICHAIN_UNIVERSAL_ROUTER_ADDRESS
        )
        universal_router_address = validate_contract_address(router_address)
        universal_router_abi = load_abi_if_not_exist(
            logger, UNICHAIN_UNIVERSAL_ROUTER_ADDRESS, CHAINID_UNICHAIN
        )  # same contract for testnet
        self.universal_router_contract = self.web3.eth.contract(
            address=universal_router_address, abi=universal_router_abi
        )
        # Uniswap commands / actions prepare for execute_trade
        self.commands = encode_packed(["uint8"], [COMMAND_V4_SWAP])
        self.actions = encode_packed(
            ["uint8", "uint8", "uint8"],
            [0x06, 0x0C, 0x0F],  # Actions: SWAP_EXACT_IN_SINGLE, SETTLE_ALL, TAKE_ALL
        )

    def estimate_swap_price(self):
        """Returns {"bid":bid, "ask":ask} for active trading pair (notional values)"""
        input_amount = int(TOKEN0_INPUT * 10 ** int(TOKEN0_DECIMALS))  # convert to wei
        pool_rates = self._fetch_single_pool_rate(
            self.active_trading_pool, input_amount
        )
        return pool_rates

    def _fetch_single_pool_rate(self, pool, input_amount):
        token0_id = pool["token0"]["id"]
        token1_id = pool["token1"]["id"]
        fee_tier = int(pool["feeTier"])
        tick_spacing = int(pool["tickSpacing"])

        token_out_amount = get_amounts_out(
            self.uniswap_v4_quoter_contract,
            token0_id,
            token1_id,
            input_amount,
            fee_tier,
            tick_spacing,
        )

        self.token_in_amount = get_amounts_in(
            self.uniswap_v4_quoter_contract,
            token0_id,
            token1_id,
            input_amount,
            fee_tier,
            tick_spacing,
        )
        return (token_out_amount, self.token_in_amount)  # (bid, ask)

    def execute_trade(self, side):
        """
        Executes uniswap leg
        Returns full tx receipt as dict
        """
        if side == "BUY":
            zero_for_one = False
            amount_in = self.token_in_amount  # ref. to init above
        elif side == "SELL":
            zero_for_one = True
            amount_in = int(TOKEN0_INPUT * 10 ** int(TOKEN0_DECIMALS))  # convert to wei
        else:
            raise ValueError(f"Side invalid: '{side}'")

        if amount_in is None:
            raise ValueError("No value for amount_in")

        # SWAP_EXACT_IN_SINGLE params
        min_amount_out = 0  # TODO: risk management
        exact_input_single_params = encode(
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
                self.unichain_eth_native_address,  # currency0
                self.unichain_usdc_address,  # currency1
                500,  # fee (uint24)
                10,  # tickSpacing (int24)
                "0x0000000000000000000000000000000000000000",  # poolHooks
                zero_for_one,  # zeroForOne
                amount_in,  # amountIn
                min_amount_out,  # minAmountOut
                b"",  # hookData
            ],
        )

        # SETTLE_ALL params
        params_1 = encode(
            ["address", "uint128"],
            [
                (
                    self.unichain_eth_native_address
                    if zero_for_one
                    else self.unichain_usdc_address
                ),
                amount_in,
            ],  # change asset for BUY/SELL
        )

        # TAKE_ALL params
        params_2 = encode(
            ["address", "uint128"],
            [
                (
                    self.unichain_usdc_address
                    if zero_for_one
                    else self.unichain_eth_native_address
                ),
                min_amount_out,
            ],  # change asset for BUY/SELL
        )
        inputs = [
            encode(
                ["bytes", "bytes[]"],
                [self.actions, [exact_input_single_params, params_1, params_2]],
            )
        ]

        # 1. build tx
        tx = self.universal_router_contract.functions.execute(
            self.commands, inputs
        ).build_transaction(
            {
                "from": Web3.to_checksum_address(self.wallet_address),
                "value": amount_in if zero_for_one else 0,
                "nonce": self.web3.eth.get_transaction_count(self.wallet_address),
                "gas": 1_000_000,  # higher gas limit for swaps
                "maxFeePerGas": 600_000,
                "type": "0x2",
                "maxPriorityFeePerGas": 100_000,  # avg priority fee
                "chainId": self.chain_id,
            }
        )

        # 2. sign tx
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)

        # 3. send tx
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

        return receipt

    async def _fetch_pool_rates(self, pool):
        """Fetch rates for a single pool asynchronously"""
        try:
            # dynamic input adjustment
            token0_decimals = int(pool["token0"]["decimals"])
            input_amounts = [10 ** (token0_decimals - 2), 10 ** (token0_decimals - 3)]

            pool_result = {
                "pool_id": pool["id"],
                "feeTier": pool["feeTier"],
                "token0.symbol": pool["token0"]["symbol"],
                "token1.symbol": pool["token1"]["symbol"],
                "token0.id": pool["token0"]["id"],
                "token1.id": pool["token1"]["id"],
                "rates": {},
            }
            # Compute rates for each token0 input amount
            for amount_token0 in input_amounts:
                token_out_amount = await asyncio.to_thread(
                    get_amounts_out,
                    self.uniswap_v4_quoter_contract,
                    pool["token0"]["id"],
                    pool["token1"]["id"],
                    amount_token0,
                    int(pool["feeTier"]),
                    int(pool["tickSpacing"]),
                )
                token_in_amount = await asyncio.to_thread(
                    get_amounts_in,
                    self.uniswap_v4_quoter_contract,
                    pool["token0"]["id"],
                    pool["token1"]["id"],
                    amount_token0,
                    int(pool["feeTier"]),
                    int(pool["tickSpacing"]),
                )
                pool_result["rates"][amount_token0] = {
                    "bid": token_out_amount,
                    "ask": token_in_amount,
                }
            return pool_result
        except Exception as e:
            self.logger.error(
                f"❌ Error fetching swap rates for pool {pool['id']}: {e}"
            )
            return None

    async def _get_swap_rates(self):
        """Fetch swap rates for all pools asynchronously"""
        tasks = [self._fetch_pool_rates(pool) for pool in self.pools]
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)
        # Filter out any failed requests (None results)
        return [result for result in results if result is not None]
