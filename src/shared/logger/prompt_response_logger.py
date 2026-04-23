"""Dedicated prompt/response logging for debugging LLM calls.

Logs complete prompts and responses to a separate file for debugging
and analysis purposes. Each user query gets a unique session ID, and
all LLM operations within that query are numbered sequentially.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from src.shared.logger.logger_config import LoggerConfig


class PromptResponseLogger:
    """Log all LLM prompts and responses to dedicated debug file.

    Provides clear visual separation between different user queries,
    with numbered operations within each query session.
    """

    _instance: Optional["PromptResponseLogger"] = None
    _log_file: Optional[Path] = None
    _current_query_id: Optional[str] = None
    _current_query_text: Optional[str] = None
    _operation_counter: int = 0

    def __new__(cls):
        """Singleton pattern to ensure single log file."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the prompt response logger."""
        if self._initialized:
            return

        self._initialized = True
        self._current_query_id = None
        self._current_query_text = None
        self._operation_counter = 0
        self._ensure_log_file()

    def _ensure_log_file(self) -> Path:
        """Ensure log file exists for current date in src/shared/logger/ subdirectory."""
        log_dir = LoggerConfig._get_current_log_dir()
        logger_dir = log_dir / "src" / "logger"
        logger_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = logger_dir / "prompt_response.log"
        return self._log_file

    def start_query_session(self, user_query: str) -> str:
        """
        Start a new query session. Call this when a new user query is received.

        Args:
            user_query: The user's original query text

        Returns:
            The generated query session ID
        """
        self._current_query_id = str(uuid.uuid4())[:8]
        self._current_query_text = user_query
        self._operation_counter = 0

        # Log the query session header
        self._ensure_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header = f"""
{"#" * 100}
{"#" * 100}
##  NEW USER QUERY
##  Session ID: {self._current_query_id}
##  Timestamp: {timestamp}
##  Query: {user_query[:200]}{"..." if len(user_query) > 200 else ""}
{"#" * 100}
{"#" * 100}
"""
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(header)
        except Exception as e:
            print(f"Warning: Failed to log query session header: {e}")

        return self._current_query_id

    def end_query_session(self, final_response: Optional[str] = None) -> None:
        """
        End the current query session. Call this when the response is complete.

        Args:
            final_response: Optional final response sent to user
        """
        if not self._current_query_id:
            return

        self._ensure_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        footer = f"""
{"~" * 100}
##  END OF QUERY SESSION: {self._current_query_id}
##  Total Operations: {self._operation_counter}
##  Completed: {timestamp}
"""
        if final_response:
            truncated = (
                final_response[:500] + "..."
                if len(final_response) > 500
                else final_response
            )
            footer += f"##  Final Response Preview:\n{truncated}\n"

        footer += f"{'~' * 100}\n\n\n"

        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(footer)
        except Exception as e:
            print(f"Warning: Failed to log query session footer: {e}")

        self._current_query_id = None
        self._current_query_text = None
        self._operation_counter = 0

    def log_interaction(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        token_usage: Dict[str, int],
        metadata: Optional[Dict] = None,
        query_id: Optional[str] = None,
    ) -> None:
        """
        Log complete LLM interaction to file.

        Args:
            operation: Operation type (e.g., "routing", "generation", "hyde")
            system_prompt: System prompt sent to LLM
            user_prompt: User prompt sent to LLM
            response: LLM response text
            token_usage: Token counts dict with input/output/total
            metadata: Optional additional metadata
            query_id: Optional query identifier (ignored, uses session ID)
        """
        self._ensure_log_file()
        self._operation_counter += 1

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        input_tokens = token_usage.get("input_tokens", 0)
        output_tokens = token_usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens

        # Build operation header with session context
        session_info = (
            f"[Session: {self._current_query_id}]"
            if self._current_query_id
            else "[No Session]"
        )
        op_num = f"Op #{self._operation_counter}"

        log_entry = f"""
╔{"═" * 98}╗
║  {session_info} {op_num} - {operation.upper()}
║  Timestamp: {timestamp}
║  Tokens: {input_tokens} in + {output_tokens} out = {total_tokens} total
╠{"═" * 98}╣
║  SYSTEM PROMPT:
╟{"─" * 98}╢
{system_prompt}
╟{"─" * 98}╢
║  USER PROMPT:
╟{"─" * 98}╢
{user_prompt}
╟{"─" * 98}╢
║  RESPONSE:
╟{"─" * 98}╢
{response}
"""
        if metadata:
            log_entry += f"""╟{"─" * 98}╢
║  METADATA:
╟{"─" * 98}╢
{json.dumps(metadata, indent=2, default=str)}
"""
        log_entry += f"╚{'═' * 98}╝\n"

        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Warning: Failed to log prompt/response: {e}")

    def log_image_interaction(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        token_usage: Dict[str, int],
        image_path: Optional[str] = None,
        media_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Log LLM interaction with image input.

        Args:
            operation: Operation type
            system_prompt: System prompt
            user_prompt: User prompt
            response: LLM response
            token_usage: Token counts
            image_path: Path to image file (logged, not content)
            media_type: Image media type
            metadata: Additional metadata
        """
        # Add image info to metadata
        image_metadata = metadata or {}
        if image_path:
            image_metadata["image_path"] = image_path
        if media_type:
            image_metadata["media_type"] = media_type

        self.log_interaction(
            operation=operation,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            token_usage=token_usage,
            metadata=image_metadata,
        )


# Singleton accessor
_prompt_logger_instance: Optional[PromptResponseLogger] = None


def get_prompt_response_logger() -> PromptResponseLogger:
    """
    Get the singleton PromptResponseLogger instance.

    Returns:
        PromptResponseLogger instance
    """
    global _prompt_logger_instance
    if _prompt_logger_instance is None:
        _prompt_logger_instance = PromptResponseLogger()
    return _prompt_logger_instance
