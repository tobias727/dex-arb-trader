class InsufficientBalanceError(Exception):
    """Raised when the balance is insufficient."""


class QuoteError(Exception):
    """Raised when quote fails."""


class IPChangeError(Exception):
    """Raised when there is an error with IP"""


class RetrieveAbiError(Exception):
    """Raised when loading ABI fails"""


class ExecutionError(Exception):
    """Raised when execution failed"""
