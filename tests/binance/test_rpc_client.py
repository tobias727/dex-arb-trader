from unittest.mock import patch, Mock
import hmac
import hashlib
import requests
import pytest
from src.config import (
    TOKEN1_DECIMALS,
    BINANCE_FEE,
)
from src.binance.rpc_client import BinanceClientRpc
from tests.utils.dummy_logger import DummyLogger


class TestBinanceClientRpc:
    """Test for BinanceClientRpc"""

    client = BinanceClientRpc(logger=DummyLogger(), token0_input=1, testnet=True)

    @patch("requests.get")
    def test_get_price_success(self, mock_get):
        """Test successful response get_price"""
        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None  # no exception
        mock_resp.json.return_value = {
            "bids": [["100.12345678", "1.0"]],
            "asks": [["100.23456789", "1.0"]],
        }
        mock_get.return_value = mock_resp

        bid, ask = self.client.get_price()

        expected_notional_bid = int(
            (100.12345678 * 10**TOKEN1_DECIMALS) * (1 - BINANCE_FEE)
        )
        expected_notional_ask = int(
            (100.23456789 * 10**TOKEN1_DECIMALS) * (1 + BINANCE_FEE)
        )

        # Assert correct scaling
        assert bid == expected_notional_bid
        assert ask == expected_notional_ask

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

    def test_sign_payload_correct_signature(self):
        """Test that the payload is correctly signed"""
        api_params = (
            "symbol=ETHUSDC&side=BUY&type=MARKET&quantity=0.01&timestamp=1234567890"
        )
        expected_signature = hmac.new(
            self.client.binance_api_secret.encode("utf-8"),
            api_params.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        expected_result = f"{api_params}&signature={expected_signature}"
        result = self.client._sign_payload(api_params)
        assert result == expected_result

    def test_sign_payload_empty_payload(self):
        """Test signing an empty payload"""
        api_params = ""
        expected_signature = hmac.new(
            self.client.binance_api_secret.encode("utf-8"),
            api_params.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        expected_result = f"&signature={expected_signature}"
        result = self.client._sign_payload(api_params)
        assert result == expected_result

    @patch("requests.post")
    def test_execute_trade_success(self, mock_post):
        """Test successful trade execution"""
        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None  # no exception
        mock_resp.json.return_value = {"status": "FILLED"}
        mock_post.return_value = mock_resp

        result = self.client.execute_trade(side="BUY", input_amount=10)

        assert result["status"] == "FILLED"

    @patch("requests.post")
    def test_execute_trade_http_error(self, mock_post):
        """Test HTTPError exception during execution"""
        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(text="Bad Request")
        )
        mock_post.return_value = mock_resp

        with pytest.raises(requests.exceptions.HTTPError) as e:
            self.client.execute_trade(side="BUY", input_amount=10)

        assert e.type == requests.exceptions.HTTPError
