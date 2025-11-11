class IPChangeError(Exception):
    """Raised when there is an error with IP"""


class RetrieveAbiError(Exception):
    """Raised when loading ABI fails"""


class ExecutionError(Exception):
    """Raised when execution failed"""
