import pytest
from src.utils.utils import check_pre_conditions
from src.utils.types import NotionalValues
from src.utils.exceptions import InsufficientBalanceError
from tests.utils.dummy_logger import DummyLogger


class TestUtils:
    """Test for util functions"""

    notional = NotionalValues(
        b_bid=41_000_000, b_ask=41_000_100, u_bid=41_500_000, u_ask=41_600_000
    )

    def test_check_pre_conditions_sufficient_balances(self):
        """Test for sufficient balances"""
        logger = DummyLogger()
        balances = {
            "binance": {"USDC": 200.0, "ETH": 1.0},
            "uniswap": {"USDC": 150.0, "ETH": 8.0},
        }
        b_side = "BUY"
        u_side = "SELL"
        buffer = 1.01

        # no exceptions expected
        check_pre_conditions(logger, balances, b_side, u_side, self.notional, buffer)
        assert len(logger.get_logs("error")) == 0, "There should be no errors logged."

    def test_check_pre_conditions_binance_insufficient_balance(self):
        """Test for insufficient USDC on Binance for BUY."""
        logger = DummyLogger()
        balances = {
            "binance": {"USDC": 30.0, "ETH": 0.1},  # Insufficient USDC
            "uniswap": {"USDC": 150, "ETH": 0.8},
        }
        b_side = "BUY"
        u_side = "SELL"
        buffer = 1.01

        with pytest.raises(InsufficientBalanceError) as exc_info:
            check_pre_conditions(
                logger, balances, b_side, u_side, self.notional, buffer
            )

        # Validate that correct exception is raised
        assert "Binance USDC insufficient" in str(exc_info.value)

        # Ensure logger logged the exact error message
        assert len(logger.get_logs("error")) == 1, "An error should be logged."
        assert "Binance USDC insufficient" in logger.get_last_log("error")

    def test_check_pre_conditions_uniswap_insufficient_balance(self):
        """Test for insufficient ETH on Uniswap for SELL."""
        logger = DummyLogger()
        balances = {
            "binance": {"USDC": 200.0, "ETH": 1.0},
            "uniswap": {"USDC": 150.0, "ETH": 0.001},  # Insufficient ETH
        }
        b_side = "BUY"
        u_side = "SELL"
        buffer = 1.01

        with pytest.raises(InsufficientBalanceError) as exc_info:
            check_pre_conditions(
                logger, balances, b_side, u_side, self.notional, buffer
            )

        # Validate that correct exception is raised
        assert "Uniswap ETH insufficient" in str(exc_info.value)

        # Ensure logger logged the exact error message
        assert len(logger.get_logs("error")) == 1, "An error should be logged."
        assert "Uniswap ETH insufficient" in logger.get_last_log("error")

    def test_check_pre_conditions_custom_buffer(self):
        """Test for custom buffer with sufficient balances."""
        logger = DummyLogger()
        balances = {
            "binance": {"USDC": 151.0, "ETH": 2.0},
            "uniswap": {"USDC": 110.0, "ETH": 7.0},
        }
        b_side = "BUY"
        u_side = "SELL"
        buffer = 1.1  # Custom buffer

        # No exceptions expected
        check_pre_conditions(logger, balances, b_side, u_side, self.notional, buffer)

        # Ensure no errors are logged
        assert len(logger.get_logs("error")) == 0, "There should be no errors logged."
