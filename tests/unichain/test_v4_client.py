from src.unichain.clients.v4client import UnichainV4Client
from src.stream_data import load_pools
from tests.utils.dummy_logger import DummyLogger


class TestUnichainV4Client:
    """Test for v4 client"""
    pools_filepath = "unichain_v4_pools.json"
    pools = load_pools(pools_filepath)
    client = UnichainV4Client(pools, DummyLogger())

    def test_estimate_swap_price(self):
        pass
