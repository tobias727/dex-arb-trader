import os
import yaml
from dotenv import load_dotenv
from web3 import Web3


def load_config(filepath):
    """Load deployment config"""
    with open(filepath, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def validate_eth_address(address: str) -> str:
    """Validates and converts an Ethereum address to checksum format"""
    if not Web3.is_address(address):
        raise ValueError(f"Invalid Ethereum address provided: {address}")
    return Web3.to_checksum_address(address)


load_dotenv()
config = load_config("values.yaml")

OUTPUT_DIRECTORY = os.path.join(os.getcwd(), "out")

# Envs
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
INFURA_API_KEY = os.getenv("INFURA_API_KEY")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_KEY_ED25519 = os.getenv("BINANCE_API_KEY_ED25519")
BINANCE_API_KEY_TESTNET = os.getenv("BINANCE_API_KEY_TESTNET")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
BINANCE_API_SECRET_TESTNET = os.getenv("BINANCE_API_SECRET_TESTNET")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
WALLET_ADDRESS_TESTNET = os.getenv("WALLET_ADDRESS_TESTNET")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PRIVATE_KEY_TESTNET = os.getenv("PRIVATE_KEY_TESTNET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Unichain (Mainnet)
UNICHAIN_CHAINID = config["unichain"]["chain_id"]
UNICHAIN_SEQUENCER_RPC_URL = config["unichain"]["sequencer_rpc_url"]
UNICHAIN_RPC_URL = config["unichain"]["rpc_url"]
UNICHAIN_FLASHBLOCKS_WS_URL = config["unichain"]["flashblocks_ws_url"]
## Contract addresses
UNICHAIN_UNIVERSAL_ROUTER_ADDRESS = validate_eth_address(
    config["unichain"]["uniswap"]["contract_deployments"]["universal_router"]
)
UNICHAIN_UNISWAP_PERMIT2 = validate_eth_address(
    config["unichain"]["uniswap"]["contract_deployments"]["permit2"]
)
UNICHAIN_POOL_MANAGER = validate_eth_address(
    config["unichain"]["uniswap"]["contract_deployments"]["pool_manager"]
)
TICK_BITMAP_HELPER_ADDRESS = validate_eth_address(
    config["unichain"]["uniswap"]["contract_deployments"]["tick_bitmap_helper"]
)
## Token addresses
UNICHAIN_USDC = validate_eth_address(config["unichain"]["uniswap"]["tokens"]["usdc"])
UNICHAIN_ETH_NATIVE = validate_eth_address(
    config["unichain"]["uniswap"]["tokens"]["eth_native"]
)

# Binance
BINANCE_URI_REST = config["binance"]["uri_rest"]
BINANCE_URI_SBE = config["binance"]["uri_sbe"]

# Execution
VERSION = config["execution"]["version"]
TOKEN0_INPUT = config["execution"]["token0_input"]
TOKEN0_DECIMALS = config["execution"]["token0_decimals"]
TOKEN1_DECIMALS = config["execution"]["token1_decimals"]
BINANCE_FEE = config["execution"]["binance_fee"]
MIN_EDGE = config["execution"]["min_edge"]
GAS_RESERVE = config["execution"]["gas_reserve"]
UNISWAP_POOL_ID = config["execution"]["uniswap_pool_id"]

# ABIs
UNIVERSAL_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "bytes", "name": "commands", "type": "bytes"},
            {"internalType": "bytes[]", "name": "inputs", "type": "bytes[]"},
        ],
        "name": "execute",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    }
]
V4_QUOTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {
                        "components": [
                            {
                                "internalType": "Currency",
                                "name": "currency0",
                                "type": "address",
                            },
                            {
                                "internalType": "Currency",
                                "name": "currency1",
                                "type": "address",
                            },
                            {"internalType": "uint24", "name": "fee", "type": "uint24"},
                            {
                                "internalType": "int24",
                                "name": "tickSpacing",
                                "type": "int24",
                            },
                            {
                                "internalType": "contract IHooks",
                                "name": "hooks",
                                "type": "address",
                            },
                        ],
                        "internalType": "struct PoolKey",
                        "name": "poolKey",
                        "type": "tuple",
                    },
                    {"internalType": "bool", "name": "zeroForOne", "type": "bool"},
                    {
                        "internalType": "uint128",
                        "name": "exactAmount",
                        "type": "uint128",
                    },
                    {"internalType": "bytes", "name": "hookData", "type": "bytes"},
                ],
                "internalType": "struct IV4Quoter.QuoteExactSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {
                        "components": [
                            {
                                "internalType": "Currency",
                                "name": "currency0",
                                "type": "address",
                            },
                            {
                                "internalType": "Currency",
                                "name": "currency1",
                                "type": "address",
                            },
                            {"internalType": "uint24", "name": "fee", "type": "uint24"},
                            {
                                "internalType": "int24",
                                "name": "tickSpacing",
                                "type": "int24",
                            },
                            {
                                "internalType": "contract IHooks",
                                "name": "hooks",
                                "type": "address",
                            },
                        ],
                        "internalType": "struct PoolKey",
                        "name": "poolKey",
                        "type": "tuple",
                    },
                    {"internalType": "bool", "name": "zeroForOne", "type": "bool"},
                    {
                        "internalType": "uint128",
                        "name": "exactAmount",
                        "type": "uint128",
                    },
                    {"internalType": "bytes", "name": "hookData", "type": "bytes"},
                ],
                "internalType": "struct IV4Quoter.QuoteExactSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactOutputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]
TICK_BITMAP_HELPER_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "poolId", "type": "bytes32"},
            {"internalType": "int16", "name": "startWord", "type": "int16"},
            {"internalType": "int16", "name": "endWord", "type": "int16"},
        ],
        "name": "getTickBitmapsRange",
        "outputs": [
            {"internalType": "uint256[]", "name": "bitmaps", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "poolId", "type": "bytes32"},
            {"internalType": "int24[]", "name": "tickIndices", "type": "int24[]"},
        ],
        "name": "getTicks",
        "outputs": [
            {
                "components": [
                    {"internalType": "int24", "name": "index", "type": "int24"},
                    {
                        "internalType": "uint128",
                        "name": "liquidityGross",
                        "type": "uint128",
                    },
                    {
                        "internalType": "int128",
                        "name": "liquidityNet",
                        "type": "int128",
                    },
                    {
                        "internalType": "uint256",
                        "name": "feeGrowthOutside0X128",
                        "type": "uint256",
                    },
                    {
                        "internalType": "uint256",
                        "name": "feeGrowthOutside1X128",
                        "type": "uint256",
                    },
                ],
                "internalType": "struct TickBitmapHelper.TickData[]",
                "name": "ticks",
                "type": "tuple[]",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]
ERC20_ABI = [
    {
        "constant": "true",
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]
