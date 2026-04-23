"""Detailed retrieval call logging for debugging and analysis.

Logs complete retrieval operation details including:
- Query text and search parameters
- Retrieved documents with scores
- Search configuration (k, threshold, filters)
- Latency metrics
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from src.shared.logger.logger_config import LoggerConfig


class RetrievalLogger:
    """Log all retrieval operations with detailed results.

    Provides session-based logging for tracking retrieval
    workflows within user query processing.
    """

    _instance: Optional["RetrievalLogger"] = None
    _log_file: Optional[Path] = None
    
    # Context variables for async/thread safety
    import contextvars
    # Context variables for session identification
    _current_session_id_var = contextvars.ContextVar("retrieval_session_id", default=None)
    
    # Shared counters across threads/tasks (keyed by session_id)
    _session_counters = {}

    def __new__(cls):
        """Singleton pattern to ensure single log file."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the retrieval logger."""
        if self._initialized:
            return

        self._initialized = True
        self._ensure_log_file()

    def _ensure_log_file(self) -> Path:
        """Ensure log file exists for current date in src/shared/logger/ subdirectory."""
        log_dir = LoggerConfig._get_current_log_dir()
        logger_dir = log_dir / "src" / "logger"
        logger_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = logger_dir / "retrieval_calls.log"
        return self._log_file

    def start_session(self, session_id: str = "", context: str = "") -> str:
        """Start a new logging session or continue an existing one.

        Args:
            session_id: Optional session ID to use (uses first 8 chars for display)
            context: Optional context for the session

        Returns:
            The session ID being used
        """
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
##  NEW RETRIEVAL SESSION
##  Session ID: {display_session_id}
##  Timestamp: {timestamp}
##  Context: {context[:200]}{"..." if len(context) > 200 else ""}
{"#" * 100}
{"#" * 100}
"""
        try:
            self._write_to_file(header)
        except Exception as e:
            print(f"Warning: Failed to log retrieval session header: {e}")

        return display_session_id

    async def a_start_session(self, session_id: str = "", context: str = "") -> str:
        """Start a new logging session or continue an existing one (Async).

        Args:
            session_id: Optional session ID to use (uses first 8 chars for display)
            context: Optional context for the session

        Returns:
            The session ID being used
        """
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
##  NEW RETRIEVAL SESSION
##  Session ID: {display_session_id}
##  Timestamp: {timestamp}
##  Context: {context[:200]}{"..." if len(context) > 200 else ""}
{"#" * 100}
{"#" * 100}
"""
        try:
            await asyncio.to_thread(self._write_to_file, header)
        except Exception as e:
            print(f"Warning: Failed to log retrieval session header: {e}")

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
##  END OF RETRIEVAL SESSION: {session_id}
##  Total Retrieval Calls: {self._session_counters.get(session_id, 0)}
##  Completed: {timestamp}
{"~" * 100}


"""
        try:
            self._write_to_file(footer)
        except Exception as e:
            print(f"Warning: Failed to log retrieval session footer: {e}")

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
##  END OF RETRIEVAL SESSION: {session_id}
##  Total Retrieval Calls: {self._session_counters.get(session_id, 0)}
##  Completed: {timestamp}
{"~" * 100}


"""
        try:
            await asyncio.to_thread(self._write_to_file, footer)
        except Exception as e:
            print(f"Warning: Failed to log retrieval session footer: {e}")

        # Don't pop the counter - allows follow-up queries to detect active session
        # self._session_counters.pop(session_id, None)
        self._current_session_id_var.set(None)

    def log_retrieval(
        self,
        query: str,
        k: int,
        results: List[Dict],
        use_hybrid: bool = False,
        use_mmr: bool = False,
        score_threshold: float = 0.0,
        source_filter: Optional[str] = None,
        latency_ms: float = 0.0,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Log a retrieval operation with full details.

        Args:
            query: The search query
            k: Number of results requested
            results: List of retrieved documents
            use_hybrid: Whether hybrid search was used
            use_mmr: Whether MMR diversity was applied
            score_threshold: Minimum score threshold
            source_filter: Source filter if applied
            latency_ms: Operation latency in milliseconds
            metadata: Optional additional metadata
        """
        self._ensure_log_file()
        
        session_id = self._current_session_id_var.get()
        if session_id:
            self._session_counters[session_id] = self._session_counters.get(session_id, 0) + 1
            counter = self._session_counters[session_id]
        else:
            counter = 0

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = self._current_session_id_var.get()
        session_info = (
            f"Session: {session_id}"
            if session_id
            else "No Session"
        )

        search_mode = []
        if use_hybrid:
            search_mode.append("Hybrid")
        if use_mmr:
            search_mode.append("MMR")
        if not search_mode:
            search_mode.append("Dense")
        mode_str = "+".join(search_mode)

        log_entry = f"""
{"#" * 100}
## RETRIEVAL #{counter} | {timestamp}
## {session_info}
## Query: "{query[:100]}{"..." if len(query) > 100 else ""}"
## K={k} | Mode={mode_str} | Threshold={score_threshold} | Latency: {latency_ms:.2f} ms
{"#" * 100}

=== SEARCH PARAMETERS ===
Query: {query}
K: {k}
Hybrid Search: {use_hybrid}
MMR Diversity: {use_mmr}
Score Threshold: {score_threshold}
Source Filter: {source_filter or "None"}

=== RETRIEVED DOCUMENTS ({len(results)} results) ===
"""
        for i, doc in enumerate(results, 1):
            score = doc.get("score", 0)
            source = doc.get("source", "unknown")
            page = doc.get("page", 0)
            header = doc.get("header", "")
            content = doc.get("content", "")
            content_preview = content[:300] + "..." if len(content) > 300 else content

            log_entry += f"""
[{i}] Score: {score:.4f} | Source: {source} | Page: {page}
    Header: {header}
    Content: {content_preview}
"""

        if metadata:
            log_entry += f"""
=== METADATA ===
{json.dumps(metadata, indent=2, default=str)}
"""
        log_entry += f"""
===== END RETRIEVAL #{counter} =====

"""

        try:
            self._write_to_file(log_entry)
        except Exception as e:
            print(f"Warning: Failed to log retrieval: {e}")

    async def a_log_retrieval(
        self,
        query: str,
        k: int,
        results: List[Dict],
        use_hybrid: bool = False,
        use_mmr: bool = False,
        score_threshold: float = 0.0,
        source_filter: Optional[str] = None,
        latency_ms: float = 0.0,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Log a retrieval operation (Async)."""
        self._ensure_log_file()
        
        session_id = self._current_session_id_var.get()
        if session_id:
            self._session_counters[session_id] = self._session_counters.get(session_id, 0) + 1
            counter = self._session_counters[session_id]
        else:
            counter = 0

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = self._current_session_id_var.get()
        session_info = (
            f"Session: {session_id}"
            if session_id
            else "No Session"
        )

        search_mode = []
        if use_hybrid:
            search_mode.append("Hybrid")
        if use_mmr:
            search_mode.append("MMR")
        if not search_mode:
            search_mode.append("Dense")
        mode_str = "+".join(search_mode)

        log_entry = f"""
{"#" * 100}
## RETRIEVAL #{counter} | {timestamp}
## {session_info}
## Query: "{query[:100]}{"..." if len(query) > 100 else ""}"
## K={k} | Mode={mode_str} | Threshold={score_threshold} | Latency: {latency_ms:.2f} ms
{"#" * 100}

=== SEARCH PARAMETERS ===
Query: {query}
K: {k}
Hybrid Search: {use_hybrid}
MMR Diversity: {use_mmr}
Score Threshold: {score_threshold}
Source Filter: {source_filter or "None"}

=== RETRIEVED DOCUMENTS ({len(results)} results) ===
"""
        for i, doc in enumerate(results, 1):
            score = doc.get("score", 0)
            source = doc.get("source", "unknown")
            page = doc.get("page", 0)
            header = doc.get("header", "")
            content = doc.get("content", "")
            content_preview = content[:300] + "..." if len(content) > 300 else content

            log_entry += f"""
[{i}] Score: {score:.4f} | Source: {source} | Page: {page}
    Header: {header}
    Content: {content_preview}
"""

        if metadata:
            log_entry += f"""
=== METADATA ===
{json.dumps(metadata, indent=2, default=str)}
"""
        log_entry += f"""
===== END RETRIEVAL #{counter} =====

"""

        try:
            await asyncio.to_thread(self._write_to_file, log_entry)
        except Exception as e:
            print(f"Warning: Failed to log retrieval: {e}")

    def log_reranking(
        self,
        query: str,
        original_results: List[Dict],
        reranked_results: List[Dict],
        latency_ms: float = 0.0,
    ) -> None:
        """Log a reranking operation.

        Args:
            query: The search query
            original_results: Results before reranking
            reranked_results: Results after reranking
            latency_ms: Reranking latency
        """
        self._ensure_log_file()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_entry = f"""
{"─" * 100}
## RERANKING | {timestamp} | Latency: {latency_ms:.2f} ms
## Query: "{query[:100]}{"..." if len(query) > 100 else ""}"
{"─" * 100}

Original Order -> Reranked Order:
"""
        for i, doc in enumerate(reranked_results, 1):
            original_pos = next(
                (
                    j + 1
                    for j, d in enumerate(original_results)
                    if d.get("id") == doc.get("id")
                ),
                "?",
            )
            log_entry += f"  [{original_pos}] -> [{i}] Score: {doc.get('score', 0):.4f} | {doc.get('source', 'unknown')}\n"

        log_entry += f"""
{"─" * 100}

"""

        try:
            self._write_to_file(log_entry)
        except Exception as e:
            print(f"Warning: Failed to log reranking: {e}")

    async def a_log_reranking(
        self,
        query: str,
        original_results: List[Dict],
        reranked_results: List[Dict],
        latency_ms: float = 0.0,
    ) -> None:
        """Log a reranking operation (Async)."""
        self._ensure_log_file()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_entry = f"""
{"─" * 100}
## RERANKING | {timestamp} | Latency: {latency_ms:.2f} ms
## Query: "{query[:100]}{"..." if len(query) > 100 else ""}"
{"─" * 100}

Original Order -> Reranked Order:
"""
        for i, doc in enumerate(reranked_results, 1):
            original_pos = next(
                (
                    j + 1
                    for j, d in enumerate(original_results)
                    if d.get("id") == doc.get("id")
                ),
                "?",
            )
            log_entry += f"  [{original_pos}] -> [{i}] Score: {doc.get('score', 0):.4f} | {doc.get('source', 'unknown')}\n"

        log_entry += f"""
{"─" * 100}

"""

        try:
            await asyncio.to_thread(self._write_to_file, log_entry)
        except Exception as e:
            print(f"Warning: Failed to log reranking: {e}")


_retrieval_logger_instance: Optional[RetrievalLogger] = None


def get_retrieval_logger() -> RetrievalLogger:
    """Get the singleton RetrievalLogger instance.

    Returns:
        RetrievalLogger instance
    """
    global _retrieval_logger_instance
    if _retrieval_logger_instance is None:
        _retrieval_logger_instance = RetrievalLogger()
    return _retrieval_logger_instance
