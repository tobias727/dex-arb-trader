class DummyLogger:
    """Dummy logger for testing purposes."""

    def __init__(self):
        self.logs = {"info": [], "error": [], "debug": [], "warning": []}

    def info(self, msg, *args, **kwargs):
        """Log an info message (support formatted messages)."""
        formatted_msg = msg % args if args else msg
        self.logs["info"].append(formatted_msg)
        print(formatted_msg)

    def error(self, msg, *args, **kwargs):
        """Log an error message (support formatted messages)."""
        formatted_msg = msg % args if args else msg
        self.logs["error"].append(formatted_msg)
        print(formatted_msg)

    def debug(self, msg, *args, **kwargs):
        """Log a debug message."""
        formatted_msg = msg % args if args else msg
        self.logs["debug"].append(formatted_msg)
        print(formatted_msg)

    def warning(self, msg, *args, **kwargs):
        """Log a warning message."""
        formatted_msg = msg % args if args else msg
        self.logs["warning"].append(formatted_msg)
        print(formatted_msg)

    def get_logs(self, level):
        """Retrieve logs by level ('info', 'error', 'debug', 'warning')."""
        return self.logs.get(level, [])

    def get_last_log(self, level):
        """Retrieve the last log message of a given level."""
        return self.logs.get(level, [])[-1] if self.logs.get(level) else None
