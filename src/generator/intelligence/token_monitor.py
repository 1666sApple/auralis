"""Token monitoring for LangChain LLM callbacks."""

from typing import Dict, Any, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from src.generator.intelligence.llm_utils import extract_token_usage

class TokenTrackingCallback(BaseCallbackHandler):
    """Callback handler for tracking token usage."""

    def __init__(self, token_tracker=None, operation: str = None):
        self.token_tracker = token_tracker
        self.operation = operation
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Track tokens when LLM call completes."""
        # LLMResult contains a list of generations
        # Each generation might have metadata, and the whole result has llm_output
        token_usage = extract_token_usage(response)
        self.input_tokens = token_usage["input_tokens"]
        self.output_tokens = token_usage["output_tokens"]

        if self.token_tracker and self.operation:
            self.token_tracker.track_llm_call(
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                operation=self.operation,
            )
