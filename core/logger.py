"""
Centralized Logging Module for XLIFF AI Assistant.

Provides consistent logging across all modules with output to:
- Console (for development/debugging)
- File (logs/xliff_assistant.log for post-crash analysis)
"""
import logging
import os
import sys
from datetime import datetime

# Create logs directory if not exists
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "xliff_assistant.log")

# Formatter with timestamp, level, module, and message
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(funcName)s() | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance.
    
    Args:
        name: Usually __name__ of the calling module.
        
    Returns:
        A logging.Logger instance configured for file and console output.
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # File Handler - captures everything (DEBUG and above)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    # Console Handler - only INFO and above for cleaner output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Module-level convenience: log uncaught exceptions
def setup_exception_hook():
    """
    Installs a global exception hook to log uncaught exceptions before crash.
    Call this once at app startup.
    """
    root_logger = get_logger("CRASH")
    
    def exception_hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow Ctrl+C to exit without logging
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        root_logger.critical("Uncaught exception!", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    
    sys.excepthook = exception_hook
