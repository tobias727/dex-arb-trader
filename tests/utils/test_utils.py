import pytest
from src.utils.utils import check_pre_trade, calculate_input_amounts
from src.utils.types import NotionalValues, InputAmounts
from src.utils.exceptions import InsufficientBalanceError
from tests.utils.dummy_logger import DummyLogger

TOKEN0_INPUT = 0.002
BINANCE_MIN_NOTIONAL = 5.0
BINANCE_STEP_SIZE = 0.0001
BINANCE_MIN_QTY = 0.0001
GAS_RESERVE = 0.000001


class TestUtils:
    """Test for util functions"""

    notional = NotionalValues(
        b_bid=41_000_000, b_ask=41_000_100, u_bid=41_500_000, u_ask=41_600_000
    )

    def test_check_pre_trade_sufficient_balances(self):
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
        check_pre_trade(logger, balances, b_side, u_side, self.notional, buffer)
        assert len(logger.get_logs("error")) == 0, "There should be no errors logged."

    def test_check_pre_trade_binance_insufficient_balance(self):
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
            check_pre_trade(
                logger, balances, b_side, u_side, self.notional, buffer
            )

        # Validate that correct exception is raised
        assert "Binance USDC insufficient" in str(exc_info.value)

        # Ensure logger logged the exact error message
        assert len(logger.get_logs("error")) == 1, "An error should be logged."
        assert "Binance USDC insufficient" in logger.get_last_log("error")

    def test_check_pre_trade_uniswap_insufficient_balance(self):
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
            check_pre_trade(
                logger, balances, b_side, u_side, self.notional, buffer
            )

        # Validate that correct exception is raised
        assert "Uniswap ETH insufficient" in str(exc_info.value)

        # Ensure logger logged the exact error message
        assert len(logger.get_logs("error")) == 1, "An error should be logged."
        assert "Uniswap ETH insufficient" in logger.get_last_log("error")

    def test_check_pre_trade_custom_buffer(self):
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
        check_pre_trade(logger, balances, b_side, u_side, self.notional, buffer)

        # Ensure no errors are logged
        assert len(logger.get_logs("error")) == 0, "There should be no errors logged."

    def test_cex_bux_dex_sell(self):
        """cex_bux_dex_sell"""
        balances = {
            "binance": {"ETH": 0.00098100, "USDC": 55.85459253},
            "uniswap": {"ETH": 0.014549167019999025, "USDC": 0.0},
        }
        current_price = 4_500

        amounts = calculate_input_amounts(balances, current_price)
        print(amounts)
        assert isinstance(amounts, InputAmounts)
        assert amounts.binance_buy == pytest.approx(0.002)
        assert amounts.binance_sell is None
        assert amounts.uniswap_buy is None
        assert amounts.uniswap_sell == pytest.approx(0.002)

    def test_all(self):
        """all possible"""
        balances = {
            "binance": {"ETH": 0.01098100, "USDC": 10.85459253},
            "uniswap": {"ETH": 0.004549167019999025, "USDC": 45.452335},
        }
        current_price = 4_500

        amounts = calculate_input_amounts(balances, current_price)
        print(amounts)
        assert isinstance(amounts, InputAmounts)
        assert amounts.binance_buy == pytest.approx(0.002)
        assert amounts.binance_sell == pytest.approx(0.0109)
        assert amounts.uniswap_buy == pytest.approx(45.452335)
        assert amounts.uniswap_sell == pytest.approx(0.002)

    def test_cex_sell_dex_buy(self):
        """cex_sell_dex_buy"""
        balances = {
            "binance": {"ETH": 0.01098100, "USDC": 1.85459253},
            "uniswap": {"ETH": 0.004549167019999025, "USDC": 45.452335},
        }
        current_price = 4_500

        amounts = calculate_input_amounts(balances, current_price)
        print(amounts)
        assert isinstance(amounts, InputAmounts)
        assert amounts.binance_buy is None
        assert amounts.binance_sell == pytest.approx(0.0109)
        assert amounts.uniswap_buy == pytest.approx(45.452335)
        assert amounts.uniswap_sell is None
