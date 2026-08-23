import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """Setup logger with console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Clear any existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
            )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler
    if log_file is None:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"invoice_processor_{timestamp}.log"

    try:
        file_handler = logging.FileHandler(log_file)
        file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception:
        pass  # Can't create file handler

    return logger


# Create a default logger
default_logger = setup_logger("invoice_processor")
