import time


def elapsed_ms(start_time: float) -> str:
    """Return elapsed time since start in ms, formatted in brackets."""
    return f"[ET { (time.perf_counter() - start_time) * 1000:.1f} ms]"
