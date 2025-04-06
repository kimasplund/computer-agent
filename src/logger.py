"""
Logging module for the Computer Agent application.
Provides a centralized approach to logging with different log levels and formats.
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Union
import datetime
from .config import LOG_DIR, LOG_FILE

# Create log directory if it doesn't exist
LOG_DIR.mkdir(exist_ok=True, parents=True)

# Configure logging levels
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

# Default log format
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Track loggers to avoid duplicate configuration
_loggers: Dict[str, logging.Logger] = {}


def get_logger(
    name: str, 
    level: Union[str, int] = 'INFO',
    log_file: Optional[Path] = LOG_FILE,
    log_format: str = DEFAULT_LOG_FORMAT,
    console_output: bool = True,
    max_bytes: int = 5242880,  # 5MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Get a logger with the specified name and configuration.
    
    Args:
        name: Name of the logger.
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL, or corresponding int values)
        log_file: Log file path. If None, no file logging will be configured.
        log_format: Format string for log messages.
        console_output: Whether to output logs to console.
        max_bytes: Maximum size in bytes before rotating log file.
        backup_count: Number of backup log files to keep.
        
    Returns:
        Configured logger instance.
    """
    # Return existing logger if already configured
    if name in _loggers:
        return _loggers[name]
    
    # Create new logger
    logger = logging.getLogger(name)
    
    # Set log level
    if isinstance(level, str):
        log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    else:
        log_level = level
    logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Create and configure handlers
    handlers = []
    
    # Add file handler if log_file is specified
    if log_file:
        try:
            # Create directory if it doesn't exist
            log_file.parent.mkdir(exist_ok=True, parents=True)
            
            # Create rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8',
            )
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except Exception as e:
            print(f"Error configuring file logger: {e}")
    
    # Add console handler if console_output is True
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
    
    # Add handlers to logger
    for handler in handlers:
        logger.addHandler(handler)
    
    # Store logger for reuse
    _loggers[name] = logger
    
    return logger


def log_system_info(logger: logging.Logger) -> None:
    """Log system information."""
    logger.info("=" * 40)
    logger.info(f"Application start: {datetime.datetime.now().isoformat()}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Log directory: {LOG_DIR}")
    try:
        from . import __version__
        logger.info(f"Application version: {__version__}")
    except ImportError:
        logger.info("Application version: unknown")
    logger.info("=" * 40)


def log_exception(
    logger: logging.Logger,
    exception: Exception,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an exception with additional context.
    
    Args:
        logger: Logger to use.
        exception: Exception to log.
        context: Additional context information.
    """
    context_str = ""
    if context:
        context_str = " ".join([f"{k}={v}" for k, v in context.items()])
    
    logger.exception(f"Exception: {str(exception)} {context_str}")


# Create default application logger
app_logger = get_logger('computer_agent')


# Log application start
def initialize_logging() -> None:
    """Initialize logging for the application."""
    log_system_info(app_logger) 