"""LangChain-based LLM wrapper for agent operations.

This wrapper provides the same interface as BedrockClient but uses
LangChain for LLM operations, enabling easier integration with
LangChain's ecosystem (chains, agents, callbacks, etc.).
"""

import os
import boto3
import asyncio
import time
import threading
from typing import Dict, Optional, Tuple, Generator, Any, List

# Corporate proxy settings are managed by the system environment.

from langchain_aws import ChatBedrockConverse

from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger
from src.shared.logger.llm_call_logger import get_llm_call_logger
from src.generator.intelligence.token_monitor import TokenTrackingCallback
from src.shared.utils.token_tracker import get_token_tracker
from src.shared.utils.auth_helper import get_boto3_client
from src.generator.intelligence.llm_utils import (
    extract_token_usage, 
    prepare_messages, 
    parse_response_content
)

import os
os.environ["NO_PROXY"] = "amazonaws.com,*.amazonaws.com,169.254.169.254,localhost,127.0.0.1"
os.environ["no_proxy"] = "amazonaws.com,*.amazonaws.com,169.254.169.254,localhost,127.0.0.1"
# Unset any proxy for boto3 — boto3 has its own proxy resolution
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

logger = get_logger(__name__)

# ── Concurrency Control ──────────────────────────────────────────────
# Limits how many parallel LangGraph nodes can hit Bedrock simultaneously.
# AWS Bedrock on-demand typically supports 2-5 concurrent invocations per model.
# Setting to 3 provides a safe balance between parallelism and rate limits.
MAX_CONCURRENT_LLM_CALLS = 5
_llm_semaphore = threading.Semaphore(MAX_CONCURRENT_LLM_CALLS)

# Retry configuration for throttled requests
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2  # Exponential backoff: 2s, 4s, 8s


class LangChainLLM:
    """
    LangChain-based LLM client with BedrockClient-compatible interface.

    This class provides the same method signatures as BedrockClient
    so it can be used as a drop-in replacement in the agents module.
    """

    def __init__(
        self,
        model_id: str = None,
        region_name: str = None,
        token_tracker=None,
        temperature: float = None,
        max_tokens: int = 8192,
    ):
        """
        Initialize LangChain LLM client.

        Args:
            model_id: Bedrock model ID. Defaults to settings.LLM_MODEL_ID.
            region_name: AWS region. Defaults to settings.AWS_REGION.
            token_tracker: Optional TokenTracker for usage tracking.
            temperature: Default temperature.
            max_tokens: Default max tokens for responses.
        """
        self.model_id = model_id or settings.LLM_MODEL_ID
        self.region_name = region_name or settings.AWS_REGION
        self.token_tracker = token_tracker
        self.default_temperature = temperature or getattr(
            settings, "LLM_TEMPERATURE", 0
        )
        self.default_max_tokens = max_tokens

        # Create standard LLM client
        self._bedrock_client = self._create_boto_client(self.region_name)
        self._llm = self._create_langchain_client(
            self.model_id, self._bedrock_client
        )

        # Create Vision LLM client (Nova Pro)
        self._vision_bedrock_client = self._create_boto_client(
            settings.AWS_REGION_IMAGE
        )
        self._vision_llm = self._create_langchain_client(
            settings.IMAGE_MODEL_ID, self._vision_bedrock_client
        )

        logger.info(
            f"LangChainLLM initialized - Model: {self.model_id}, "
            f"Region: {self.region_name}"
        )

    def _create_boto_client(self, region_name: str):
        """Create a boto3 bedrock-runtime client."""
        return get_boto3_client("bedrock-runtime", region_name=region_name)

    def _create_langchain_client(self, model_id: str, client: Any) -> ChatBedrockConverse:
        """Create a LangChain ChatBedrockConverse instance."""
        kwargs = {
            "model_id": model_id,
            "client": client,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
        }

        # Enable Extended Thinking for supported models (e.g., moonshot.kimi-k2-thinking, claude-3-7)
        if "thinking" in model_id.lower() or "sonnet-3-7" in model_id.lower() or "sonnet-4-5" in model_id.lower():
            kwargs["additional_model_request_fields"] = {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": getattr(settings, "LLM_THINKING_BUDGET", 2000)
                }
            }
            logger.info(f"Extended Thinking enabled for model: {model_id} with budget: {kwargs['additional_model_request_fields']['thinking']['budget_tokens']}")

        return ChatBedrockConverse(**kwargs)

    def _get_llm_for_request(self, use_vision_model: bool = False):
        """Select appropriate LLM instance."""
        return self._vision_llm if use_vision_model else self._llm

    def invoke_vision_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes: Optional[bytes] = None,
        image_format: str = "png",
        temperature: float = None,
        max_tokens: int = None,
        track_as: str = "vision_processing",
    ) -> Tuple[str, Dict[str, int]]:
        """Invoke the dedicated Vision LLM model."""
        return self._execute_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_bytes=image_bytes,
            image_format=image_format,
            temperature=temperature,
            max_tokens=max_tokens,
            track_as=track_as,
            use_vision_model=True
        )

    def invoke_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes: Optional[bytes] = None,
        image_format: str = "png",
        temperature: float = None,
        max_tokens: int = None,
        track_as: str = None,
        track_metadata: Dict = None,
        model_id: str = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Invoke LLM and return response with token usage."""
        return self._execute_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_bytes=image_bytes,
            image_format=image_format,
            temperature=temperature,
            max_tokens=max_tokens,
            track_as=track_as,
            track_metadata=track_metadata,
            use_vision_model=False,
            model_id=model_id
        )

    def _execute_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes: Optional[bytes] = None,
        image_format: str = "png",
        temperature: float = None,
        max_tokens: int = None,
        track_as: str = None,
        track_metadata: Dict = None,
        use_vision_model: bool = False,
        model_id: str = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Unified internal method for LLM execution with concurrency control and retry."""
        # Prepare messages outside the semaphore to minimize lock time
        messages = prepare_messages(
            system_prompt, user_prompt, image_bytes, image_format
        )

        # Configure runtime args
        model_kwargs = {
            "temperature": temperature or self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
        }

        # Select model
        if model_id:
            client_to_use = self._create_langchain_client(
                model_id,
                self._vision_bedrock_client if use_vision_model else self._bedrock_client
            )
        else:
            client_to_use = self._get_llm_for_request(use_vision_model)

        llm_bound = client_to_use.bind(**model_kwargs)

        # ── Concurrency-controlled execution with retry ──
        last_exception = None
        for attempt in range(1, MAX_RETRIES + 1):
            _llm_semaphore.acquire()
            try:
                logger.debug(
                    f"[Semaphore] Acquired slot (attempt {attempt}/{MAX_RETRIES}). "
                    f"Operation: {track_as or 'llm_invocation'}"
                )
                start_time = time.time()
                response = llm_bound.invoke(messages, config={"callbacks": []})
                latency_ms = (time.time() - start_time) * 1000

                # Process output
                token_usage = extract_token_usage(response)
                final_content = parse_response_content(response.content)

                # Track
                if self.token_tracker and track_as:
                    self.token_tracker.track_llm_call(
                        input_tokens=token_usage["input_tokens"],
                        output_tokens=token_usage["output_tokens"],
                        operation=track_as,
                        metadata=track_metadata or {},
                    )

                # Detailed Logging
                try:
                    get_llm_call_logger().log_call(
                        operation=track_as or "llm_invocation",
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        response=final_content,
                        token_usage=token_usage,
                        latency_ms=latency_ms,
                        metadata={**(track_metadata or {}), "model_id": model_id or self.model_id}
                    )
                except Exception as e:
                    logger.warning(f"Failed to log detailed LLM call: {e}")

                return final_content, token_usage

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                is_throttled = any(keyword in error_str for keyword in [
                    "throttl", "rate", "too many requests", "429", "limit", "capacity"
                ])

                if is_throttled and attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        f"[Throttled] Bedrock rate limit hit (attempt {attempt}/{MAX_RETRIES}). "
                        f"Retrying in {delay}s... Error: {e}"
                    )
                    time.sleep(delay)
                elif attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY_SECONDS
                    logger.warning(
                        f"[Retry] LLM call failed (attempt {attempt}/{MAX_RETRIES}). "
                        f"Retrying in {delay}s... Error: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"LangChainLLM execution failed after {MAX_RETRIES} attempts: {e}",
                        exc_info=True
                    )
            finally:
                _llm_semaphore.release()
                logger.debug(f"[Semaphore] Released slot. Operation: {track_as or 'llm_invocation'}")

        raise last_exception

    def invoke_llm_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = None,
        max_tokens: int = None,
    ) -> Generator:
        """Invoke LLM with streaming response."""
        try:
            messages = prepare_messages(system_prompt, user_prompt)

            model_kwargs = {
                "temperature": temperature or self.default_temperature,
                "max_tokens": max_tokens or self.default_max_tokens,
            }

            llm_bound = self._llm.bind(**model_kwargs)
            
            start_time = time.time()
            total_output = ""
            actual_usage = None
            for chunk in llm_bound.stream(messages):
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    actual_usage = chunk.usage_metadata
                
                if chunk.content:
                    chunk_text = parse_response_content(chunk.content)
                    if chunk_text:
                        total_output += chunk_text
                        yield chunk_text
            
            latency_ms = (time.time() - start_time) * 1000

            # Use actual usage if available, else estimate
            if actual_usage:
                usage = {
                    "input_tokens": actual_usage.get("input_tokens", 0),
                    "output_tokens": actual_usage.get("output_tokens", 0),
                    "total_tokens": actual_usage.get("total_tokens", 0),
                }
            else:
                input_tokens_est = len(system_prompt.split()) + len(user_prompt.split())
                output_tokens_est = len(total_output.split())
                usage = {
                    "input_tokens": int(input_tokens_est * 1.3),
                    "output_tokens": int(output_tokens_est * 1.3),
                    "total_tokens": int((input_tokens_est + output_tokens_est) * 1.3),
                }

            # Track in TokenTracker
            if self.token_tracker:
                self.token_tracker.track_llm_call(
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    operation="generation_stream",
                    metadata={"model_id": self.model_id}
                )

            # Detailed Logging
            try:
                get_llm_call_logger().log_call(
                    operation="generation_stream",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response=total_output,
                    token_usage=usage,
                    latency_ms=latency_ms,
                    metadata={"model_id": self.model_id}
                )
            except Exception as e:
                logger.warning(f"Failed to log detailed LLM stream call: {e}")

            yield (None, usage)

        except Exception as e:
            logger.error(f"LangChainLLM stream failed: {e}", exc_info=True)
            raise

    async def ainvoke_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes: Optional[bytes] = None,
        image_format: str = "png",
        temperature: float = None,
        max_tokens: int = None,
        track_as: str = None,
        track_metadata: Dict = None,
        model_id: str = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Async version of invoke_llm."""
        try:
            return await asyncio.to_thread(
                self.invoke_llm,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_bytes=image_bytes,
                image_format=image_format,
                temperature=temperature,
                max_tokens=max_tokens,
                track_as=track_as,
                track_metadata=track_metadata,
                model_id=model_id
            )


        except Exception as e:
            logger.error(f"LangChainLLM async invoke failed: {e}", exc_info=True)
            raise

    async def astream_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = None,
        max_tokens: int = None,
    ):
        """Async streaming version."""
        try:
            messages = prepare_messages(system_prompt, user_prompt)

            model_kwargs = {
                "temperature": temperature or self.default_temperature,
                "max_tokens": max_tokens or self.default_max_tokens,
            }

            llm = self._llm.bind(**model_kwargs)
            start_time = time.time()
            total_output = ""
            actual_usage = None
            
            async for chunk in llm.astream(messages):
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    actual_usage = chunk.usage_metadata

                if chunk.content:
                    chunk_text = parse_response_content(chunk.content)
                    if chunk_text:
                        total_output += chunk_text
                        yield chunk_text
            
            latency_ms = (time.time() - start_time) * 1000

            # Use actual usage if available, else estimate
            if actual_usage:
                usage = {
                    "input_tokens": actual_usage.get("input_tokens", 0),
                    "output_tokens": actual_usage.get("output_tokens", 0),
                    "total_tokens": actual_usage.get("total_tokens", 0),
                }
            else:
                input_tokens_est = len(system_prompt.split()) + len(user_prompt.split())
                output_tokens_est = len(total_output.split())
                usage = {
                    "input_tokens": int(input_tokens_est * 1.3),
                    "output_tokens": int(output_tokens_est * 1.3),
                    "total_tokens": int((input_tokens_est + output_tokens_est) * 1.3),
                }

            # Track in TokenTracker
            if self.token_tracker:
                self.token_tracker.track_llm_call(
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    operation="generation_stream",
                    metadata={"model_id": self.model_id}
                )

            # Detailed Logging
            try:
                await get_llm_call_logger().a_log_call(
                    operation="generation_stream",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response=total_output,
                    token_usage=usage,
                    latency_ms=latency_ms,
                    metadata={"model_id": self.model_id}
                )
            except Exception as e:
                logger.warning(f"Failed to log stream call: {e}")

            # Return usage as last item
            yield (None, usage)

        except Exception as e:
            logger.error(f"LangChainLLM async stream failed: {e}", exc_info=True)
            raise

    async def abatch_invoke(self, requests: List[Dict], max_concurrency: int = 5) -> List[Tuple[str, Dict[str, int]]]:
        """
        Invoke LLM in batches with controlled concurrency.

        Args:
            requests: List of request dicts (kwrgs for ainvoke_llm).
            max_concurrency: Maximum number of concurrent calls.

        Returns:
            List of results (same format as ainvoke_llm).
        """
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _bounded_invoke(req_kwargs):
            async with semaphore:
                try:
                    return await self.ainvoke_llm(**req_kwargs)
                except Exception as e:
                    logger.error(f"Batch item failed: {e}")
                    # Return error structure or raise
                    return ("", {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "error": str(e)})

        try:
            results = await asyncio.gather(*[_bounded_invoke(req) for req in requests])
            return results
        except Exception as e:
            logger.error(f"Batch execution failed: {e}", exc_info=True)
            raise

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the configured model."""
        return {
            "model_id": self.model_id,
            "region": self.region_name,
            "default_temperature": self.default_temperature,
            "default_max_tokens": self.default_max_tokens,
            "provider": "langchain_aws",
        }


# Singleton instance
_langchain_llm_instance: Optional[LangChainLLM] = None


def get_langchain_llm(token_tracker=None) -> LangChainLLM:
    """Get the singleton LangChainLLM instance."""
    global _langchain_llm_instance
    if _langchain_llm_instance is None:
        if token_tracker is None:
            token_tracker = get_token_tracker()
        _langchain_llm_instance = LangChainLLM(token_tracker=token_tracker)
    return _langchain_llm_instance
