"""Detailed LLM call logging for debugging and analysis.

Logs complete request/response details for every LLM call including:
- System and user prompts
- Model response
- Token usage and cost estimation
- Latency metrics
- Call metadata (operation type, caller module)
"""

import asyncio
import contextvars
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from src.shared.logger.logger_config import LoggerConfig


class LLMCallLogger:
    """Log all LLM calls with detailed prompt/response information.

    Provides session-based logging with operation numbering for
    tracking multi-step LLM workflows.
    """

    _instance: Optional["LLMCallLogger"] = None
    _log_file: Optional[Path] = None
    
    # Context variables for async safety
    # Context variables for session identification
    _current_session_id_var = contextvars.ContextVar("llm_session_id", default=None)
    
    # Shared counters across threads/tasks (keyed by session_id)
    _session_counters = {}

    def __new__(cls):
        """Singleton pattern to ensure single log file."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the LLM call logger."""
        self._initialized = True
        self._ensure_log_file()

    def _ensure_log_file(self) -> Path:
        """Ensure log file exists for current date in src/shared/logger/ subdirectory."""
        log_dir = LoggerConfig._get_current_log_dir()
        logger_dir = log_dir / "src" / "logger"
        logger_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = logger_dir / "llm_calls.log"
        return self._log_file

    def start_session(self, session_id: str = "", context: str = "") -> str:
        """Start a new logging session or continue an existing one.

        Args:
            session_id: Optional session ID to use (uses first 8 chars for display)
            context: Optional context for the session (e.g., user query)

        Returns:
            The session ID being used
        """
        import uuid
        # Use provided session_id (truncated) or generate new one
        display_session_id = session_id[:8] if session_id else str(uuid.uuid4())[:8]
        
        # Check if this session is already active - if so, continue without new header
        current_session = self._current_session_id_var.get()
        if current_session == display_session_id and display_session_id in self._session_counters:
            # Session already active, just continue
            return display_session_id
        
        self._current_session_id_var.set(display_session_id)
        self._session_counters[display_session_id] = 0

        self._ensure_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header = f"""
{"#" * 100}
{"#" * 100}
##  NEW LLM SESSION
##  Session ID: {display_session_id}
##  Timestamp: {timestamp}
##  Context: {context[:200]}{"..." if len(context) > 200 else ""}
{"#" * 100}
{"#" * 100}
"""
        try:
            # Sync write - fine for session start
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(header)
        except Exception as e:
            print(f"Warning: Failed to log LLM session header: {e}")

        return display_session_id

    async def a_start_session(self, session_id: str = "", context: str = "") -> str:
        """Start a new logging session or continue an existing one (Async).

        Args:
            session_id: Optional session ID to use (uses first 8 chars for display)
            context: Optional context for the session (e.g., user query)

        Returns:
            The session ID being used
        """
        import uuid
        # Use provided session_id (truncated) or generate new one
        display_session_id = session_id[:8] if session_id else str(uuid.uuid4())[:8]
        
        # Check if this session was already started - if so, continue without new header
        # Note: We only check the counter, not current_session, because end_session resets the var
        if display_session_id in self._session_counters:
            # Session already started, continue without new header
            self._current_session_id_var.set(display_session_id)
            return display_session_id
        
        self._current_session_id_var.set(display_session_id)
        self._session_counters[display_session_id] = 0

        self._ensure_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header = f"""
{"#" * 100}
{"#" * 100}
##  NEW LLM SESSION
##  Session ID: {display_session_id}
##  Timestamp: {timestamp}
##  Context: {context[:200]}{"..." if len(context) > 200 else ""}
{"#" * 100}
{"#" * 100}
"""
        try:
            await asyncio.to_thread(self._write_to_file, header)
        except Exception as e:
            print(f"Warning: Failed to log LLM session header: {e}")

        return display_session_id

    def _write_to_file(self, content: str) -> None:
        """Helper to write to log file synchronously."""
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(content)

    def end_session(self) -> None:
        """End the current logging session."""
        session_id = self._current_session_id_var.get()
        if not session_id:
            return

        self._ensure_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        footer = f"""
{"~" * 100}
##  END OF LLM SESSION: {session_id}
##  Total LLM Calls: {self._session_counters.get(session_id, 0)}
##  Completed: {timestamp}
{"~" * 100}


"""
        try:
            self._write_to_file(footer)
        except Exception as e:
            print(f"Warning: Failed to log LLM session footer: {e}")

        # Don't pop the counter - allows follow-up queries to detect active session
        # self._session_counters.pop(session_id, None)
        self._current_session_id_var.set(None)

    async def a_end_session(self) -> None:
        """End the current logging session (Async)."""
        session_id = self._current_session_id_var.get()
        if not session_id:
            return

        self._ensure_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        footer = f"""
{"~" * 100}
##  END OF LLM SESSION: {session_id}
##  Total LLM Calls: {self._session_counters.get(session_id, 0)}
##  Completed: {timestamp}
{"~" * 100}


"""
        try:
            await asyncio.to_thread(self._write_to_file, footer)
        except Exception as e:
            print(f"Warning: Failed to log LLM session footer: {e}")

        # Don't pop the counter - allows follow-up queries to detect active session
        # self._session_counters.pop(session_id, None)
        self._current_session_id_var.set(None)

    def log_call(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        token_usage: Dict[str, int],
        latency_ms: float = 0.0,
        metadata: Optional[Dict] = None,
        reasoning_content: Optional[str] = None,
    ) -> None:
        """Log a complete LLM call with all details.

        Args:
            operation: Operation type (e.g., "query_analysis", "generation")
            system_prompt: System prompt sent to LLM
            user_prompt: User prompt sent to LLM
            response: LLM response text
            token_usage: Token counts dict with input/output/total
            latency_ms: Call latency in milliseconds
            metadata: Optional additional metadata
            reasoning_content: Optional Chain-of-Thought reasoning content
        """
        self._ensure_log_file()
        
        session_id = self._current_session_id_var.get()
        if session_id:
            self._session_counters[session_id] = self._session_counters.get(session_id, 0) + 1
            counter = self._session_counters[session_id]
        else:
            counter = 0

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        input_tokens = token_usage.get("input_tokens", 0)
        output_tokens = token_usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens

        session_id = self._current_session_id_var.get()
        session_info = (
            f"Session: {session_id}"
            if session_id
            else "No Session"
        )

        log_entry = f"""
{"#" * 100}
## LLM CALL #{counter} | {operation.upper()} | {timestamp}
## {session_info}
## Latency: {latency_ms:.2f} ms | Tokens: {input_tokens} in + {output_tokens} out = {total_tokens} total
{"#" * 100}

=== SYSTEM PROMPT ===
{system_prompt}

=== USER PROMPT ===
{user_prompt}
"""
        if reasoning_content:
            log_entry += f"""
=== REASONING CONTENT ===
{reasoning_content}
"""

        log_entry += f"""
=== RESPONSE ===
{response}
"""
        if metadata:
            import json
            log_entry += f"""
=== METADATA ===
{json.dumps(metadata, indent=2, default=str)}
"""
        log_entry += f"""
===== END LLM CALL #{counter} =====

"""

        try:
            self._write_to_file(log_entry)
        except Exception as e:
            print(f"Warning: Failed to log LLM call: {e}")

    async def a_log_call(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        token_usage: Dict[str, int],
        latency_ms: float = 0.0,
        metadata: Optional[Dict] = None,
        reasoning_content: Optional[str] = None,
    ) -> None:
        """Log a complete LLM call with all details (Async)."""
        self._ensure_log_file()
        
        session_id = self._current_session_id_var.get()
        if session_id:
            self._session_counters[session_id] = self._session_counters.get(session_id, 0) + 1
            counter = self._session_counters[session_id]
        else:
            counter = 0

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        input_tokens = token_usage.get("input_tokens", 0)
        output_tokens = token_usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens

        session_info = (
            f"Session: {session_id}"
            if session_id
            else "No Session"
        )

        log_entry = f"""
{"#" * 100}
## LLM CALL #{counter} | {operation.upper()} | {timestamp}
## {session_info}
## Latency: {latency_ms:.2f} ms | Tokens: {input_tokens} in + {output_tokens} out = {total_tokens} total
{"#" * 100}

=== SYSTEM PROMPT ===
{system_prompt}

=== USER PROMPT ===
{user_prompt}
"""
        if reasoning_content:
            log_entry += f"""
=== REASONING CONTENT ===
{reasoning_content}
"""

        log_entry += f"""
=== RESPONSE ===
{response}
"""
        if metadata:
            import json
            log_entry += f"""
=== METADATA ===
{json.dumps(metadata, indent=2, default=str)}
"""
        log_entry += f"""
===== END LLM CALL #{counter} =====

"""

        try:
            await asyncio.to_thread(self._write_to_file, log_entry)
        except Exception as e:
            print(f"Warning: Failed to log LLM call: {e}")

    def log_image_call(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        token_usage: Dict[str, int],
        image_path: Optional[str] = None,
        media_type: Optional[str] = None,
        latency_ms: float = 0.0,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Log an LLM call with image input.

        Args:
            operation: Operation type
            system_prompt: System prompt
            user_prompt: User prompt
            response: LLM response
            token_usage: Token counts
            image_path: Path to image file
            media_type: Image media type
            latency_ms: Call latency
            metadata: Additional metadata
        """
        image_metadata = metadata or {}
        if image_path:
            image_metadata["image_path"] = image_path
        if media_type:
            image_metadata["media_type"] = media_type

        self.log_call(
            operation=operation,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            token_usage=token_usage,
            latency_ms=latency_ms,
            metadata=image_metadata,
        )


_llm_logger_instance: Optional[LLMCallLogger] = None


def get_llm_call_logger() -> LLMCallLogger:
    """Get the singleton LLMCallLogger instance.

    Returns:
        LLMCallLogger instance
    """
    global _llm_logger_instance
    if _llm_logger_instance is None:
        _llm_logger_instance = LLMCallLogger()
    return _llm_logger_instance
