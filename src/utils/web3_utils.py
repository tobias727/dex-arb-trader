from web3 import Web3, AsyncWeb3


def connect_web3_async(rpc_url: str) -> AsyncWeb3:
    """Sync connect to a AsnycWeb3 provider."""
    return AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))


def connect_web3(rpc_url: str) -> Web3:
    """Sync connect to a Web3 provider."""
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError("Web3 not connected")
    return w3
