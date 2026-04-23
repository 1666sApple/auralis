"""Token usage tracking utility using actual Bedrock response metadata."""

from typing import Dict, Optional, List
from datetime import datetime
from collections import defaultdict
import json
from src.generator.prompts.prompt_loader import get_prompt_loader
from src.shared.logger.logger_config import get_logger
from src.shared.logger.token_consumption_logger import get_token_consumption_logger

logger = get_logger(__name__)


class TokenTracker:
    """Track token usage from actual Bedrock API responses."""

    def __init__(self):
        """Initialize TokenTracker."""
        self.usage_history: List[Dict] = []
        self.session_stats = defaultdict(int)
        self.prompt_loader = get_prompt_loader()
        logger.info("TokenTracker initialized - Using Bedrock API tokens")

    def track_usage(
        self, input_tokens: int, output_tokens: int, metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Track token usage from Bedrock response.

        Args:
            input_tokens: Input tokens from Bedrock response
            output_tokens: Output tokens from Bedrock response
            metadata: Additional metadata (query, mode, etc.)

        Returns:
            Usage statistics dictionary
        """
        total_tokens = input_tokens + output_tokens

        usage = {
            "timestamp": datetime.now().isoformat(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "metadata": metadata or {},
        }

        # Update session stats
        self.session_stats["total_calls"] += 1
        self.session_stats["total_input_tokens"] += input_tokens
        self.session_stats["total_output_tokens"] += output_tokens
        self.session_stats["total_tokens"] += total_tokens

        # Store in history
        self.usage_history.append(usage)

        logger.debug(
            f"Token usage tracked - Input: {input_tokens}, "
            f"Output: {output_tokens}, Total: {total_tokens}"
        )

        return usage

    def track_llm_call(
        self,
        input_tokens: int,
        output_tokens: int,
        operation: str,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Track a single LLM call with operation context.

        Args:
            input_tokens: Input tokens from Bedrock
            output_tokens: Output tokens from Bedrock
            operation: Operation name (e.g., 'routing', 'complexity',
                'enhancement', 'reasoning', 'summarization', 'generation')
            metadata: Additional context (query snippet, mode, etc.)

        Returns:
            Usage statistics dictionary
        """
        total_tokens = input_tokens + output_tokens

        usage = {
            "timestamp": datetime.now().isoformat(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "operation": operation,
            "metadata": metadata or {},
        }

        # Update session stats
        self.session_stats["total_calls"] += 1
        self.session_stats["total_input_tokens"] += input_tokens
        self.session_stats["total_output_tokens"] += output_tokens
        self.session_stats["total_tokens"] += total_tokens
        self.session_stats[f"calls_{operation}"] += 1
        self.session_stats[f"tokens_{operation}"] = (
            self.session_stats.get(f"tokens_{operation}", 0) + total_tokens
        )

        # Store in history
        self.usage_history.append(usage)

        logger.debug(
            f"LLM call tracked - Operation: {operation}, "
            f"Input: {input_tokens}, Output: {output_tokens}, "
            f"Total: {total_tokens}"
        )

        # Log to token consumption file
        try:
            get_token_consumption_logger().log_tokens(
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                metadata=metadata
            )
        except Exception as e:
            logger.warning(f"Failed to log tokens to consumption file: {e}")

        return usage

    def track_rag_generation(
        self,
        input_tokens: int,
        output_tokens: int,
        query: str,
        num_sources: int,
        mode: str,
    ) -> Dict:
        """
        Track token usage for RAG generation from Bedrock response.

        Args:
            input_tokens: Total input tokens from Bedrock
                (includes system + user prompts)
            output_tokens: Output tokens from Bedrock response
            query: Original user query
            num_sources: Number of source documents used
            mode: Generation mode

        Returns:
            Usage statistics dictionary
        """
        total_tokens = input_tokens + output_tokens

        usage = {
            "timestamp": datetime.now().isoformat(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "metadata": {
                "query": query[:100],  # Truncate for storage
                "num_sources": num_sources,
                "mode": mode,
                "type": "rag_generation",
            },
        }

        # Update session stats
        self.session_stats["total_calls"] += 1
        self.session_stats["total_input_tokens"] += input_tokens
        self.session_stats["total_output_tokens"] += output_tokens
        self.session_stats["total_tokens"] += total_tokens
        self.session_stats[f"calls_{mode}"] += 1

        # Store in history
        self.usage_history.append(usage)

        logger.info(
            f"RAG token usage - Mode: {mode}, Input: {input_tokens}, "
            f"Output: {output_tokens}, Total: {total_tokens}, "
            f"Sources: {num_sources}"
        )

        # Log to token consumption file
        try:
            get_token_consumption_logger().log_tokens(
                operation=f"rag_generation_{mode}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                metadata={**usage["metadata"], "original_query": query}
            )
        except Exception as e:
            logger.warning(f"Failed to log RAG tokens to consumption file: {e}")

        return usage

    def get_session_stats(self) -> Dict:
        """
        Get cumulative session statistics.

        Returns:
            Dictionary with session statistics
        """
        stats = dict(self.session_stats)

        if stats.get("total_calls", 0) > 0:
            stats["avg_input_tokens"] = (
                stats["total_input_tokens"] / stats["total_calls"]
            )
            stats["avg_output_tokens"] = (
                stats["total_output_tokens"] / stats["total_calls"]
            )
            stats["avg_total_tokens"] = stats["total_tokens"] / stats["total_calls"]

        return stats

    def get_cost_estimate(
        self,
        input_price_per_1k: float = 0.003,  # Claude 3.5 Sonnet pricing
        output_price_per_1k: float = 0.015,
    ) -> Dict:
        """
        Estimate costs based on token usage.

        Args:
            input_price_per_1k: Price per 1K input tokens
                (default: Claude 3.5 Sonnet)
            output_price_per_1k: Price per 1K output tokens
                (default: Claude 3.5 Sonnet)

        Returns:
            Cost estimate dictionary
        """
        stats = self.get_session_stats()

        input_cost = (stats.get("total_input_tokens", 0) / 1000) * input_price_per_1k
        output_cost = (stats.get("total_output_tokens", 0) / 1000) * output_price_per_1k
        total_cost = input_cost + output_cost

        return {
            "input_cost": round(input_cost, 4),
            "output_cost": round(output_cost, 4),
            "total_cost": round(total_cost, 4),
            "currency": "USD",
            "pricing": {
                "input_per_1k": input_price_per_1k,
                "output_per_1k": output_price_per_1k,
            },
        }

    def export_history(self, filepath: str) -> None:
        """
        Export usage history to JSON file.

        Args:
            filepath: Output file path
        """
        data = {
            "session_stats": self.get_session_stats(),
            "usage_history": self.usage_history,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Token usage history exported to {filepath}")

    def reset(self) -> None:
        """Reset all tracking data."""
        self.usage_history.clear()
        self.session_stats.clear()
        logger.info("Token tracker reset")

    def print_summary(self) -> None:
        """Print a formatted summary of token usage."""
        stats = self.get_session_stats()
        costs = self.get_cost_estimate()

        # Get formatting template from prompt_loader
        summary_template = self.prompt_loader.get_message("token_summary_template")

        # If template not found, use default formatting
        if not summary_template:
            self._print_default_summary(stats, costs)
            return

        # Format and print template
        try:
            formatted = summary_template.format(
                total_calls=stats.get("total_calls", 0),
                total_tokens=f"{stats.get('total_tokens', 0):,}",
                total_input_tokens=f"{stats.get('total_input_tokens', 0):,}",
                total_output_tokens=f"{stats.get('total_output_tokens', 0):,}",
                avg_input_tokens=stats.get("avg_input_tokens", 0),
                avg_output_tokens=stats.get("avg_output_tokens", 0),
                avg_total_tokens=stats.get("avg_total_tokens", 0),
                total_cost=costs["total_cost"],
                input_cost=costs["input_cost"],
                output_cost=costs["output_cost"],
            )
            print(formatted)
        except KeyError:
            self._print_default_summary(stats, costs)

    def _print_default_summary(self, stats: Dict, costs: Dict) -> None:
        """Print default summary format (fallback)."""
        print("\n" + "=" * 50)
        print("TOKEN USAGE SUMMARY (Bedrock API)")
        print("=" * 50)
        print(f"Total Calls:        {stats.get('total_calls', 0)}")
        print(f"Total Tokens:       {stats.get('total_tokens', 0):,}")
        print(f"  Input Tokens:     {stats.get('total_input_tokens', 0):,}")
        print(f"  Output Tokens:    {stats.get('total_output_tokens', 0):,}")

        if stats.get("total_calls", 0) > 0:
            print("\nAverage per Call:")
            print(f"  Input Tokens:     {stats.get('avg_input_tokens', 0):.1f}")
            print(f"  Output Tokens:    {stats.get('avg_output_tokens', 0):.1f}")
            print(f"  Total Tokens:     {stats.get('avg_total_tokens', 0):.1f}")

        print("\nEstimated Cost (Claude 3.5 Sonnet):")
        print(f"  Total Cost:       ${costs['total_cost']:.4f}")
        print(f"  Input Cost:       ${costs['input_cost']:.4f}")
        print(f"  Output Cost:      ${costs['output_cost']:.4f}")
        print("=" * 50 + "\n")


# Singleton instance
_token_tracker_instance: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    """
    Get or create TokenTracker singleton instance.

    Returns:
        TokenTracker instance
    """
    global _token_tracker_instance

    if _token_tracker_instance is None:
        _token_tracker_instance = TokenTracker()

    return _token_tracker_instance
