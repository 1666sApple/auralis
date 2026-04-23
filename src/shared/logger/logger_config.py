"""
Centralized logging configuration with daily log rotation.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import date
from typing import Optional


class LoggerConfig:
    """
    Centralized logger configuration with daily log file organization.

    All logs from the same calendar day go into a single dated directory.
    Each module gets one log file per day, reused and
    appended across application restarts.
    """

    _loggers: dict[str, logging.Logger] = {}
    _current_date: Optional[date] = None
    _current_log_dir: Optional[Path] = None

    @staticmethod
    def _get_current_log_dir(base_dir: str = "logs") -> Path:
        """
        Get or create the log directory for the current date (YYYY-MM-DD).

        Caches the directory path for the current day. If the date changes
        (e.g., application runs past midnight), it automatically switches.

        Args:
            base_dir: Base logging directory (default: "logs")

        Returns:
            Path: Absolute path to today's log directory
        """
        today = date.today()
        log_dir = Path(base_dir) / today.strftime("%Y-%m-%d")

        # Detect date change and invalidate cache if needed
        if LoggerConfig._current_date != today:
            LoggerConfig._current_date = today
            LoggerConfig._current_log_dir = log_dir
            log_dir.mkdir(parents=True, exist_ok=True)

        elif LoggerConfig._current_log_dir is None:
            LoggerConfig._current_log_dir = log_dir
            log_dir.mkdir(parents=True, exist_ok=True)

        return LoggerConfig._current_log_dir

    @staticmethod
    def setup_logger(
        name: str,
        log_level: int = logging.INFO,
        log_dir: str = "logs",
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 10,
    ) -> logging.Logger:
        """
        Configure and return a logger that writes to a daily log file.

        Log files are organized as:
            logs/
                2025-04-05/
                    module_name.log
                    another_module.log
                2025-04-06/
                    ...

        Args:
            name: Logger name (use __name__ in modules)
            log_level: Minimum logging level
            log_dir: Base directory for dated log folders
            max_bytes: Max size per log file before rotation
            backup_count: Number of rollover files to keep per day

        Returns:
            logging.Logger: Fully configured logger
        """
        if name in LoggerConfig._loggers:
            return LoggerConfig._loggers[name]

        # Ensure log directory for today exists
        daily_log_dir = LoggerConfig._get_current_log_dir(log_dir)

        logger = logging.getLogger(name)
        logger.setLevel(log_level)
        logger.propagate = True  # Enable logs to reach the terminal via uvicorn

        # Prevent adding handlers multiple times
        if logger.handlers:
            LoggerConfig._loggers[name] = logger
            return logger

        # Convert module path to directory structure
        # e.g., "src.rag_agent" -> "src/agents/rag_agent.log"
        module_parts = name.split(".")
        if len(module_parts) > 1:
            log_subdir = daily_log_dir / "/".join(module_parts[:-1])
            log_subdir.mkdir(parents=True, exist_ok=True)
            log_file = log_subdir / f"{module_parts[-1]}.log"
        else:
            log_file = daily_log_dir / f"{name}.log"

        # File handler with rotation (per day + size-based)
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)

        detailed_formatter = logging.Formatter(
            fmt="""%(asctime)s - %(name)s - %(levelname)s - \
                [%(filename)s:%(lineno)d] - %(funcName)s - %(message)s""",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(detailed_formatter)

        # Console handler
        console_formatter = logging.Formatter(
            fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        LoggerConfig._loggers[name] = logger
        return logger

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get an existing logger or create one with default settings.

        Automatically uses today's log directory and
         appends to the correct file.

        Args:
            name: Logger name (pass __name__)

        Returns:
            Configured logger instance
        """
        if name not in LoggerConfig._loggers:
            LoggerConfig.setup_logger(name)
        return LoggerConfig._loggers[name]


# Convenience function
def get_logger(name: str) -> logging.Logger:
    """
    Recommended way to get a logger in any module.

    Example:
        logger = get_logger(__name__)
        logger.info("Processing started")

    Automatically routes logs to the correct daily folder and module file.
    """
    return LoggerConfig.get_logger(name)
