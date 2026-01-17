import logging
import sys


def setup_logging(name: str = "BGP") -> logging.Logger:
    """Configures and returns a logger with standard formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Check if handler already exists to avoid duplication
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
