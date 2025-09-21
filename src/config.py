import os
import yaml
from dotenv import load_dotenv


def load_config(filepath="values.yaml"):
    """Load deployment config"""
    with open(filepath, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


load_dotenv()
config = load_config()

OUTPUT_DIRECTORY = os.path.join(os.getcwd(), "out")

# Envs
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
WALLET_ADDRESS_TESTNET = os.getenv("WALLET_ADDRESS_TESTNET")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
PRIVATE_KEY_TESTNET = os.getenv("PRIVATE_KEY_TESTNET")

# Mainnet
CHAINID_MAINNET = config["mainnet"]["chain_id"]
MAINNET_UNISWAP_V2_ROUTER_02 = config["mainnet"]["uniswap"]["v2_contract_addresses"][
    "router_02"
]
MAINNET_SUSHISWAP_ROUTER_ADDRESS = config["mainnet"]["sushiswap"]["contract_addresses"][
    "router"
]

# Unichain
CHAINID_UNICHAIN = config["unichain"]["chain_id"]
ALCHEMY_UNICHAIN_BASE_RPC_URL = config["unichain"]["alchemy_rpc_base_url"]
UNISWAP_PROTOCOL_VERSION = config["unichain"]["uniswap"]["active_protocol_version"]
UNICHAIN_UNIVERSAL_ROUTER_ADDRESS = config["unichain"]["uniswap"][
    "contract_deployments"
]["universal_router"]
UNICHAIN_V4_POOL_MANAGER = config["unichain"]["uniswap"][
    "contract_deployments"
]["v4_pool_manager"]
UNICHAIN_UNISWAP_V2_ROUTER_02 = config["unichain"]["uniswap"]["contract_deployments"][
    "v2_router_02"
]
UNICHAIN_UNISWAP_V2_FACTORY = config["unichain"]["uniswap"]["contract_deployments"][
    "v2_factory"
]
UNICHAIN_UNISWAP_V4_QUOTER = config["unichain"]["uniswap"]["contract_deployments"][
    "v4_quoter"
]
UNICHAIN_UNISWAP_V4_STATEVIEW = config["unichain"]["uniswap"]["contract_deployments"][
    "v4_stateview"
]
UNICHAIN_UNISWAP_PERMIT2 = config["unichain"]["uniswap"]["contract_deployments"][
    "permit2"
]
UNICHAIN_WETH = config["unichain"]["uniswap"]["tokens"]["weth"]
UNICHAIN_USDC = config["unichain"]["uniswap"]["tokens"]["usdc"]
UNICHAIN_ETH_NATIVE = config["unichain"]["uniswap"]["tokens"]["eth_native"]
COMMAND_V4_SWAP = config["unichain"]["uniswap"]["universal_router_commands"]["V4_SWAP"]
COMMAND_WRAP_ETH = config["unichain"]["uniswap"]["universal_router_commands"]["WRAP_ETH"]
COMMAND_UNWRAP_ETH = config["unichain"]["uniswap"]["universal_router_commands"]["UNWRAP_ETH"]
COMMAND_BALANCE_CHECK_ERC20 = config["unichain"]["uniswap"]["universal_router_commands"]["BALANCE_CHECK_ERC20"]

# Unichain testnet
CHAINID_UNICHAIN_SEPOLIA_TESTNET = config["unichain-sepolia-testnet"]["chain_id"]
ALCHEMY_UNICHAIN_SEPOLIA_RPC_URL = config["unichain-sepolia-testnet"]["rpc_url"]
UNICHAIN_SEPOLIA_ROUTER_ADDRESS = config["unichain-sepolia-testnet"]["uniswap"][
    "contract_deployments"
]["universal_router"]
UNICHAIN_SEPOLIA_WETH9 = config["unichain-sepolia-testnet"]["uniswap"]["tokens"]["weth9"]
UNICHAIN_SEPOLIA_USDC = config["unichain-sepolia-testnet"]["uniswap"]["tokens"]["usdc"]
UNICHAIN_SEPOLIA_ETH_NATIVE = config["unichain-sepolia-testnet"]["uniswap"]["tokens"]["eth_native"]
UNICHAIN_SEPOLIA_POOL_MANAGER =  config["unichain-sepolia-testnet"]["uniswap"][
    "contract_deployments"
]["pool_manager"]
UNICHAIN_SEPOLIA_STATE_VIEW =  config["unichain-sepolia-testnet"]["uniswap"][
    "contract_deployments"
]["state_view"]
UNICHAIN_SEPOLIA_PERMIT2 =  config["unichain-sepolia-testnet"]["uniswap"][
    "contract_deployments"
]["permit2"]

# Deployment
STREAM_DURATION = config["stream_duration"]
UPDATE_INTERVAL = config["binance"]["update_interval"]
ORDER_BOOK_DEPTH = config["binance"]["order_book_depth"]
BINANCE_TOKEN_PAIRS = config["binance"]["token_pairs"]
BINANCE_BASE_URL_RPC = config["binance"]["base_url_rpc"]
BINANCE_BASE_URL_WS = config["binance"]["base_url"]
LATEST = config["latest"]

# Execution
ACTIVE_TRADING_PAIR = config["execution"]["active_trading_pair"]
ACTIVE_TOKEN0 = config["execution"]["active_token0"]
ACTIVE_TOKEN1 = config["execution"]["active_token1"]
TOKEN0_INPUT = config["execution"]["token0_input"]
TOKEN0_DECIMALS = config["execution"]["token0_decimals"]
TOKEN1_DECIMALS = config["execution"]["token1_decimals"]
BINANCE_FEE = config["execution"]["binance_fee"]
MIN_EDGE = config["execution"]["min_edge"]
BINANCE_TICK_SIZE = config["execution"]["binance_tick_size"]
