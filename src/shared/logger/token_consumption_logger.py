"""Centralized token consumption logging for LLM operations.

Creates a dedicated log file that tracks token consumption at each step
of the RAG pipeline in a structured, easy-to-analyze format.
"""

import asyncio
import contextvars
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from collections import defaultdict
from src.shared.logger.logger_config import LoggerConfig


class TokenConsumptionLogger:
    """Centralized logger for token consumption across all LLM operations.

    Creates a dedicated token_consumption.log file with:
    - Per-operation token counts
    - Session-level summaries
    - Step-by-step tracking for pipeline analysis
    """

    _instance: Optional["TokenConsumptionLogger"] = None
    _log_file: Optional[Path] = None
    
    # Context variables for async safety
    _current_session_id_var = contextvars.ContextVar("token_session_id", default=None)
    # Shared counters across threads/tasks (keyed by session_id)
    _session_counters = {}
    _session_tokens: Dict[str, Dict] = {}

    def __new__(cls):
        """Singleton pattern for consistent logging."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the token consumption logger."""
        if self._initialized:
            return

        self._initialized = True
        self._ensure_log_file()

    def _ensure_log_file(self) -> Path:
        """Ensure log file exists for current date."""
        log_dir = LoggerConfig._get_current_log_dir()
        logger_dir = log_dir / "src" / "logger"
        logger_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = logger_dir / "token_consumption.log"
        return self._log_file

    def start_session(self, session_id: str, query: str = "") -> None:
        """Start tracking a new user session.

        Args:
            session_id: Unique session identifier
            query: User query for context
        """
        self._current_session_id_var.set(session_id)
        self._session_counters[session_id] = 0
        self._session_tokens[session_id] = {
            "operations": [],
            "totals": {"input": 0, "output": 0, "total": 0},
            "start_time": datetime.now().isoformat(),
            "query": query[:200] if query else "",
        }

        try:
            self._write_to_file(header)
        except Exception as e:
            print(f"Warning: Failed to log token session header: {e}")

    async def a_start_session(self, session_id: str, query: str = "") -> None:
        """Start tracking a new user session (Async)."""
        self._current_session_id_var.set(session_id)
        self._session_counters[session_id] = 0
        self._session_tokens[session_id] = {
            "operations": [],
            "totals": {"input": 0, "output": 0, "total": 0},
            "start_time": datetime.now().isoformat(),
            "query": query[:200] if query else "",
        }

        self._ensure_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header = f"""
{"=" * 80}
TOKEN CONSUMPTION SESSION | {timestamp}
Session ID: {session_id}
Query: {query[:100]}{"..." if len(query) > 100 else ""}
{"=" * 80}
{"Step":<6} {"Operation":<30} {"Input":>10} {"Output":>10} {"Total":>10}
{"-" * 80}
"""
        try:
            await asyncio.to_thread(self._write_to_file, header)
        except Exception as e:
            print(f"Warning: Failed to log token session header: {e}")

    def _write_to_file(self, content: str) -> None:
        """Helper to write to log file synchronously."""
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(content)

    def log_tokens(
        self,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, int]:
        """Log token consumption for an operation.

        Args:
            operation: Name of the operation (e.g., 'query_analysis', 'generation')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            metadata: Optional additional context

        Returns:
            Dict with token counts for this operation
        """
        self._ensure_log_file()
        
        session_id = self._current_session_id_var.get()
        if session_id:
            # Thread-safe counter increment
            self._session_counters[session_id] = self._session_counters.get(session_id, 0) + 1
            step = self._session_counters[session_id]
        else:
            step = 0
        total_tokens = input_tokens + output_tokens

        # Update session totals
        session_id = self._current_session_id_var.get()
        if session_id and session_id in self._session_tokens:
            session = self._session_tokens[session_id]
            session["totals"]["input"] += input_tokens
            session["totals"]["output"] += output_tokens
            session["totals"]["total"] += total_tokens
            session["operations"].append(
                {
                    "step": step,
                    "operation": operation,
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": total_tokens,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata,
                }
            )

        # Format and write log entry
        log_line = f"{step:<6} {operation:<30} {input_tokens:>10,} {output_tokens:>10,} {total_tokens:>10,}\n"
        try:
            self._write_to_file(log_line)
        except Exception as e:
            print(f"Warning: Failed to log tokens: {e}")

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    async def a_log_tokens(
        self,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, int]:
        """Log token consumption for an operation (Async)."""
        self._ensure_log_file()
        
        session_id = self._current_session_id_var.get()
        if session_id:
            # Thread-safe counter increment
            self._session_counters[session_id] = self._session_counters.get(session_id, 0) + 1
            step = self._session_counters[session_id]
        else:
            step = 0
        total_tokens = input_tokens + output_tokens

        # Update session totals
        if session_id and session_id in self._session_tokens:
            session = self._session_tokens[session_id]
            session["totals"]["input"] += input_tokens
            session["totals"]["output"] += output_tokens
            session["totals"]["total"] += total_tokens
            session["operations"].append(
                {
                    "step": step,
                    "operation": operation,
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": total_tokens,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata,
                }
            )

        # Format and write log entry
        log_line = f"{step:<6} {operation:<30} {input_tokens:>10,} {output_tokens:>10,} {total_tokens:>10,}\n"
        try:
            await asyncio.to_thread(self._write_to_file, log_line)
        except Exception as e:
            print(f"Warning: Failed to log tokens: {e}")

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    def end_session(self) -> Dict:
        """End the current session and write summary.

        Returns:
            Dict with session totals and operation breakdown
        """
        session_id = self._current_session_id_var.get()
        if not session_id:
            return {}

        session = self._session_tokens[session_id]
        totals = session["totals"]

        # Calculate cost estimate (Claude 3.5 Sonnet pricing)
        input_cost = (totals["input"] / 1000) * 0.003
        output_cost = (totals["output"] / 1000) * 0.015
        total_cost = input_cost + output_cost

        summary = f"""{"-" * 80}
TOTAL            {" " * 23} {totals["input"]:>10,} {totals["output"]:>10,} {totals["total"]:>10,}
{"=" * 80}
Estimated Cost: ${total_cost:.6f} (Input: ${input_cost:.6f}, Output: ${output_cost:.6f})
Operations: {len(session["operations"])}
{"=" * 80}

"""
        try:
            self._write_to_file(summary)
        except Exception as e:
            print(f"Warning: Failed to log token summary: {e}")

        result = {
            "session_id": session_id,
            "totals": totals,
            "cost_estimate": {
                "total": round(total_cost, 6),
                "input": round(input_cost, 6),
                "output": round(output_cost, 6),
            },
            "operations": session["operations"],
        }

        self._session_tokens.pop(session_id, None)
        self._session_counters.pop(session_id, None)
        self._current_session_id_var.set(None)
        return result

    async def a_end_session(self) -> Dict:
        """End the current session and write summary (Async)."""
        session_id = self._current_session_id_var.get()
        if not session_id:
            return {}

        session = self._session_tokens[session_id]
        totals = session["totals"]

        # Calculate cost estimate (Claude 3.5 Sonnet pricing)
        input_cost = (totals["input"] / 1000) * 0.003
        output_cost = (totals["output"] / 1000) * 0.015
        total_cost = input_cost + output_cost

        summary = f"""{"-" * 80}
TOTAL            {" " * 23} {totals["input"]:>10,} {totals["output"]:>10,} {totals["total"]:>10,}
{"=" * 80}
Estimated Cost: ${total_cost:.6f} (Input: ${input_cost:.6f}, Output: ${output_cost:.6f})
Operations: {len(session["operations"])}
{"=" * 80}

"""
        try:
            await asyncio.to_thread(self._write_to_file, summary)
        except Exception as e:
            print(f"Warning: Failed to log token summary: {e}")

        result = {
            "session_id": session_id,
            "totals": totals,
            "cost_estimate": {
                "total": round(total_cost, 6),
                "input": round(input_cost, 6),
                "output": round(output_cost, 6),
            },
            "operations": session["operations"],
        }

        self._session_tokens.pop(session_id, None)
        self._session_counters.pop(session_id, None)
        self._current_session_id_var.set(None)
        return result

    def get_session_summary(self, session_id: str = None) -> Dict:
        """Get summary for a session.

        Args:
            session_id: Session to summarize, defaults to current

        Returns:
            Dict with session statistics
        """
        sid = session_id or self._current_session_id_var.get()
        if not sid or sid not in self._session_tokens:
            return {}
        return self._session_tokens[sid]

    def _write_log(self, content: str) -> None:
        """Legacy write content to log file (Sync)."""
        self._write_to_file(content)


# Singleton accessor
_token_consumption_logger: Optional[TokenConsumptionLogger] = None


def get_token_consumption_logger() -> TokenConsumptionLogger:
    """Get the singleton TokenConsumptionLogger instance.

    Returns:
        TokenConsumptionLogger instance
    """
    global _token_consumption_logger
    if _token_consumption_logger is None:
        _token_consumption_logger = TokenConsumptionLogger()
    return _token_consumption_logger
