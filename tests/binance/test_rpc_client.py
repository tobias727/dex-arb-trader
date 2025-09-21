from unittest.mock import patch, Mock
import requests
import pytest
from src.config import(
    TOKEN1_DECIMALS,
)
from src.binance.rpc_client import BinanceClientRpc
from tests.utils.dummy_logger import DummyLogger


class TestBinanceClientRpc:
    """Test for BinanceClientRpc"""
    client = BinanceClientRpc(logger=DummyLogger(), token0_input=1)

    @patch("requests.get")
    def test_get_price_success(self, mock_get):
        """Test successful response get_price"""
        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None  # no exception
        mock_resp.json.return_value = {
            "bids": [["100.12345678", "1.0"]],
            "asks": [["100.23456789", "1.0"]]
        }
        mock_get.return_value = mock_resp

        bid, ask = self.client.get_price()

        # Assert correct scaling
        assert bid == int(100.12345678 * 10**TOKEN1_DECIMALS)
        assert ask == int(100.23456789 * 10**TOKEN1_DECIMALS)

    @patch("requests.get")
    def test_get_price_rate_limit_429(self, mock_get):
        """Test rate limit (429) get_price"""
        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        with pytest.raises(SystemExit) as e:
            self.client.get_price()
        assert e.type == SystemExit

    @patch("requests.get")
    def test_get_price_rate_limit_418(self, mock_get):
        """Test IP ban (418) get_price"""
        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_resp.status_code = 418
        mock_get.return_value = mock_resp

        with pytest.raises(SystemExit):
            self.client.get_price()
