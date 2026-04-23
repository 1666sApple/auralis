"""
LLM Retry Utility with Exponential Backoff.

Provides robust retry logic for LLM calls that may fail due to:
- Network issues
- Rate limiting
- Malformed responses
- JSON parsing errors
"""

import asyncio
import json
import re
from typing import Any, Callable, TypeVar, Optional
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 10.0  # seconds


class LLMRetryError(Exception):
    """Raised when all LLM retry attempts fail."""

    def __init__(self, message: str, last_error: Exception = None):
        super().__init__(message)
        self.last_error = last_error


def calculate_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap

    Returns:
        Delay in seconds
    """
    delay = base_delay * (2**attempt)
    return min(delay, max_delay)


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    request_id: Optional[str] = None,
    **kwargs,
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments to pass
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries
        max_delay: Maximum delay cap
        request_id: Optional request ID for logging
        **kwargs: Keyword arguments to pass

    Returns:
        Result of the function

    Raises:
        LLMRetryError: If all retries are exhausted
    """
    last_error = None
    prefix = f"[{request_id}] " if request_id else ""

    for attempt in range(max_retries):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return result

        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                f"{prefix}JSON parse error on attempt {attempt + 1}/{max_retries}: {e}"
            )
        except Exception as e:
            last_error = e
            logger.warning(
                f"{prefix}LLM call failed on attempt {attempt + 1}/{max_retries}: {e}"
            )

        if attempt < max_retries - 1:
            delay = calculate_backoff(attempt, base_delay, max_delay)
            logger.info(f"{prefix}Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)

    raise LLMRetryError(
        f"All {max_retries} retry attempts failed",
        last_error=last_error,
    )


def extract_json_from_response(response: str) -> dict:
    """
    Extract JSON from LLM response that may contain markdown or extra text.

    Args:
        response: Raw LLM response string

    Returns:
        Parsed JSON dictionary

    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    text = response.strip()

    # Remove markdown code fences
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # If all else fails, raise error
    raise json.JSONDecodeError("No valid JSON found in response", text, 0)


async def invoke_llm_with_retry(
    llm_client,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 8196,
    max_retries: int = DEFAULT_MAX_RETRIES,
    request_id: Optional[str] = None,
    parse_json: bool = True,
) -> Any:
    """
    Invoke LLM with retry logic and optional JSON parsing.

    Args:
        llm_client: LLM client instance
        system_prompt: System prompt for LLM
        user_prompt: User prompt for LLM
        max_tokens: Maximum tokens in response
        max_retries: Number of retry attempts
        request_id: Optional request ID for logging
        parse_json: Whether to parse response as JSON

    Returns:
        Parsed JSON dict or raw string response
    """
    prefix = f"[{request_id}] " if request_id else ""

    async def _invoke():
        if hasattr(llm_client, "invoke_llm"):
            response = await llm_client.invoke_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            )
        elif hasattr(llm_client, "invoke"):
            response = llm_client.invoke(system_prompt + "\n\n" + user_prompt)
            response = str(
                response.content if hasattr(response, "content") else response
            )
        else:
            raise ValueError("LLM client does not have invoke method")

        if parse_json:
            return extract_json_from_response(response)
        return response

    try:
        return await retry_with_backoff(
            _invoke,
            max_retries=max_retries,
            request_id=request_id,
        )
    except LLMRetryError:
        logger.error(f"{prefix}LLM invocation failed after {max_retries} attempts")
        raise
