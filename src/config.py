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
UNICHAIN_UNIVERSAL_ROUTER_V2_ADDRESS = config["unichain"]["uniswap"][
    "contract_deployments"
]["universal_router_v2"]
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
UNICHAIN_WETH = config["unichain"]["uniswap"]["tokens"]
UNICHAIN_USDC = config["unichain"]["uniswap"]["tokens"]

# Deployment
STREAM_DURATION = config["stream_duration"]
UPDATE_INTERVAL = config["binance"]["update_interval"]
ORDER_BOOK_DEPTH = config["binance"]["order_book_depth"]
BINANCE_TOKEN_PAIR = config["binance"]["token_pair"]
BINANCE_BASE_URL_WS = config["binance"]["base_url"]
