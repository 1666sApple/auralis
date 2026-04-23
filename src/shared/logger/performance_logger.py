"""Performance timing logger for API call analysis.

Logs complete timing breakdown for each API request including:
- Total request time
- Process-by-process breakdown (query analysis, retrieval, generation, etc.)
- Percentage of time per process
- Bottleneck identification
"""

import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from src.shared.logger.logger_config import LoggerConfig


@dataclass
class TimingEntry:
    """A single timing entry for a process."""

    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    children: List["TimingEntry"] = field(default_factory=list)


class PerformanceLogger:
    """Log performance timing breakdown for API calls.

    Tracks timing for each process within an API call and provides
    a clear breakdown with percentages and bottleneck identification.
    """

    _instance: Optional["PerformanceLogger"] = None
    _log_file: Optional[Path] = None

    def __new__(cls):
        """Singleton pattern to ensure single log file."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the performance logger."""
        if self._initialized:
            return

        self._initialized = True
        self._api_call_counter = 0
        self._current_timings: Dict[str, TimingEntry] = {}
        self._timing_stack: List[str] = []
        self._api_start_time: float = 0.0
        self._current_query: str = ""
        self._ensure_log_file()

    def _ensure_log_file(self) -> Path:
        """Ensure log file exists for current date in src/shared/logger/ subdirectory."""
        log_dir = LoggerConfig._get_current_log_dir()
        logger_dir = log_dir / "src" / "logger"
        logger_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = logger_dir / "performance.log"
        return self._log_file

    def _write_to_file(self, content: str) -> None:
        """Helper to write to log file synchronously."""
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(content)

    def start_api_call(self, query: str = "") -> str:
        """Start timing for a new API call.

        Args:
            query: The user query for this API call

        Returns:
            A unique call ID
        """
        self._api_call_counter += 1
        self._api_start_time = time.time()
        self._current_query = query
        self._current_timings = {}
        self._timing_stack = []
        return f"api-{self._api_call_counter}"

    def start_process(self, process_name: str) -> None:
        """Start timing for a specific process.

        Args:
            process_name: Name of the process being timed
        """
        entry = TimingEntry(name=process_name, start_time=time.time())
        self._current_timings[process_name] = entry
        self._timing_stack.append(process_name)

    def end_process(self, process_name: str) -> float:
        """End timing for a specific process.

        Args:
            process_name: Name of the process to end

        Returns:
            Duration in milliseconds
        """
        if process_name not in self._current_timings:
            return 0.0

        entry = self._current_timings[process_name]
        entry.end_time = time.time()
        entry.duration_ms = (entry.end_time - entry.start_time) * 1000

        if process_name in self._timing_stack:
            self._timing_stack.remove(process_name)

        return entry.duration_ms

    def record_process(self, process_name: str, duration_ms: float) -> None:
        """Record a process timing directly (for already-timed operations).

        Args:
            process_name: Name of the process
            duration_ms: Duration in milliseconds
        """
        entry = TimingEntry(
            name=process_name,
            duration_ms=duration_ms,
        )
        self._current_timings[process_name] = entry

    def end_api_call(self) -> None:
        """End the API call and log the complete timing breakdown."""
        total_time_ms = (time.time() - self._api_start_time) * 1000

        self._ensure_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Sort timings by duration (descending)
        sorted_timings = sorted(
            self._current_timings.values(),
            key=lambda x: x.duration_ms,
            reverse=True,
        )

        # Find bottleneck
        bottleneck = sorted_timings[0] if sorted_timings else None

        # Build timing table
        table_rows = []
        for entry in sorted_timings:
            percentage = (
                (entry.duration_ms / total_time_ms * 100) if total_time_ms > 0 else 0
            )
            table_rows.append((entry.name, entry.duration_ms, percentage))

        # Calculate tracked vs untracked time
        tracked_time = sum(e.duration_ms for e in sorted_timings)
        untracked_time = total_time_ms - tracked_time

        log_entry = f"""
{"#" * 100}
## API CALL #{self._api_call_counter} | {timestamp} | Total: {total_time_ms:.2f} ms
## Query: "{self._current_query[:100]}{"..." if len(self._current_query) > 100 else ""}"
{"#" * 100}

TIMING BREAKDOWN:
┌──────────────────────────────────────────┬────────────┬─────────┐
│ Process                                  │ Time (ms)  │ %       │
├──────────────────────────────────────────┼────────────┼─────────┤
"""

        for name, duration, percentage in table_rows:
            name_padded = name[:40].ljust(40)
            duration_str = f"{duration:10.2f}"
            percentage_str = f"{percentage:6.1f}%"
            log_entry += f"│ {name_padded} │ {duration_str} │ {percentage_str} │\n"

        # Add untracked time if significant
        if untracked_time > 10:  # More than 10ms untracked
            untracked_pct = (
                (untracked_time / total_time_ms * 100) if total_time_ms > 0 else 0
            )
            name_padded = "(Untracked/Overhead)".ljust(40)
            log_entry += (
                f"│ {name_padded} │ {untracked_time:10.2f} │ {untracked_pct:6.1f}% │\n"
            )

        log_entry += f"""├──────────────────────────────────────────┼────────────┼─────────┤
│ {"TOTAL".ljust(40)} │ {total_time_ms:10.2f} │  100.0% │
└──────────────────────────────────────────┴────────────┴─────────┘
"""

        if bottleneck and bottleneck.duration_ms > 0:
            bottleneck_pct = (
                (bottleneck.duration_ms / total_time_ms * 100)
                if total_time_ms > 0
                else 0
            )
            log_entry += f"""
BOTTLENECK: {bottleneck.name} ({bottleneck_pct:.1f}%)
"""

        log_entry += f"""
===== END API CALL #{self._api_call_counter} =====

"""

        try:
            self._write_to_file(log_entry)
        except Exception as e:
            print(f"Warning: Failed to log performance: {e}")

        # Reset for next call
        self._current_timings = {}
        self._timing_stack = []
        self._current_query = ""

    async def a_end_api_call(self) -> None:
        """End the API call and log the complete timing breakdown (Async)."""
        total_time_ms = (time.time() - self._api_start_time) * 1000

        self._ensure_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Sort timings by duration (descending)
        sorted_timings = sorted(
            self._current_timings.values(),
            key=lambda x: x.duration_ms,
            reverse=True,
        )

        # Find bottleneck
        bottleneck = sorted_timings[0] if sorted_timings else None

        # Build timing table
        table_rows = []
        for entry in sorted_timings:
            percentage = (
                (entry.duration_ms / total_time_ms * 100) if total_time_ms > 0 else 0
            )
            table_rows.append((entry.name, entry.duration_ms, percentage))

        # Calculate tracked vs untracked time
        tracked_time = sum(e.duration_ms for e in sorted_timings)
        untracked_time = total_time_ms - tracked_time

        log_entry = f"""
{"#" * 100}
## API CALL #{self._api_call_counter} | {timestamp} | Total: {total_time_ms:.2f} ms
## Query: "{self._current_query[:100]}{"..." if len(self._current_query) > 100 else ""}"
{"#" * 100}

TIMING BREAKDOWN:
┌──────────────────────────────────────────┬────────────┬─────────┐
│ Process                                  │ Time (ms)  │ %       │
├──────────────────────────────────────────┼────────────┼─────────┤
"""

        for name, duration, percentage in table_rows:
            name_padded = name[:40].ljust(40)
            duration_str = f"{duration:10.2f}"
            percentage_str = f"{percentage:6.1f}%"
            log_entry += f"│ {name_padded} │ {duration_str} │ {percentage_str} │\n"

        # Add untracked time if significant
        if untracked_time > 10:  # More than 10ms untracked
            untracked_pct = (
                (untracked_time / total_time_ms * 100) if total_time_ms > 0 else 0
            )
            name_padded = "(Untracked/Overhead)".ljust(40)
            log_entry += (
                f"│ {name_padded} │ {untracked_time:10.2f} │ {untracked_pct:6.1f}% │\n"
            )

        log_entry += f"""├──────────────────────────────────────────┼────────────┼─────────┤
│ {"TOTAL".ljust(40)} │ {total_time_ms:10.2f} │  100.0% │
└──────────────────────────────────────────┴────────────┴─────────┘
"""

        if bottleneck and bottleneck.duration_ms > 0:
            bottleneck_pct = (
                (bottleneck.duration_ms / total_time_ms * 100)
                if total_time_ms > 0
                else 0
            )
            log_entry += f"""
BOTTLENECK: {bottleneck.name} ({bottleneck_pct:.1f}%)
"""

        log_entry += f"""
===== END API CALL #{self._api_call_counter} =====

"""

        try:
            await asyncio.to_thread(self._write_to_file, log_entry)
        except Exception as e:
            print(f"Warning: Failed to log performance: {e}")

        # Reset for next call
        self._current_timings = {}
        self._timing_stack = []
        self._current_query = ""

    def get_current_timings(self) -> Dict[str, float]:
        """Get current timing data as a dictionary.

        Returns:
            Dictionary mapping process names to durations in ms
        """
        return {
            name: entry.duration_ms for name, entry in self._current_timings.items()
        }


class PerformanceTimer:
    """Context manager for timing a process.

    Usage:
        with PerformanceTimer("query_analysis"):
            # do something
    """

    def __init__(self, process_name: str, logger: Optional[PerformanceLogger] = None):
        """Initialize the timer.

        Args:
            process_name: Name of the process to time
            logger: Optional logger instance (uses singleton if not provided)
        """
        self.process_name = process_name
        self.logger = logger or get_performance_logger()
        self.duration_ms = 0.0

    def __enter__(self) -> "PerformanceTimer":
        """Start timing."""
        self.logger.start_process(self.process_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End timing."""
        self.duration_ms = self.logger.end_process(self.process_name)


_performance_logger_instance: Optional[PerformanceLogger] = None


def get_performance_logger() -> PerformanceLogger:
    """Get the singleton PerformanceLogger instance.

    Returns:
        PerformanceLogger instance
    """
    global _performance_logger_instance
    if _performance_logger_instance is None:
        _performance_logger_instance = PerformanceLogger()
    return _performance_logger_instance
