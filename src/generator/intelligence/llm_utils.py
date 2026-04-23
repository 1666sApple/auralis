"""Utilities for LangChain LLM interactions."""

import base64
from typing import Dict, List, Optional, Union, Any
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)

def extract_token_usage(response: Any) -> Dict[str, int]:
    """
    Extract token usage from LangChain response.

    Args:
        response: BaseMessage, LLMResult or standard response object.

    Returns:
        Dict with input_tokens, output_tokens, total_tokens.
    """
    usage = {}

    # 1. Try usage_metadata attribute (preferred in newer LangChain)
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        usage = response.usage_metadata
        logger.debug(f"Tokens extracted from usage_metadata: {usage}")
    # 2. Try response_metadata['usage']
    elif hasattr(response, "response_metadata"):
        meta = response.response_metadata
        usage = meta.get("usage", {})
        if not usage:
            # Some providers put it directly in meta
            usage = meta
        logger.debug(f"Tokens extracted from response_metadata: {usage}")
    # 3. Handle list of generations (from LLMResult)
    elif isinstance(response, list) and len(response) > 0 and hasattr(response[0], "usage_metadata"):
        usage = response[0].usage_metadata

    # Map possible key names
    # Input tokens
    input_tokens = (
        usage.get("prompt_tokens") or 
        usage.get("input_tokens") or 
        usage.get("inputTokens") or 
        usage.get("total_input_tokens", 0)
    )
    
    # Output tokens
    output_tokens = (
        usage.get("completion_tokens") or 
        usage.get("output_tokens") or 
        usage.get("outputTokens") or 
        usage.get("total_output_tokens", 0)
    )

    # 4. Fallback estimation if still 0
    if not input_tokens and hasattr(response, "content"):
        # This is a very rough estimate (1.3 tokens per word)
        # Note: We can't easily estimate input tokens without the full prompt here
        # so we'll just log 0 unless we have better info elsewhere
        pass

    if not output_tokens and hasattr(response, "content"):
        content_str = str(response.content)
        # Estimate 1.3 tokens per word
        output_tokens = int(len(content_str.split()) * 1.3)
        logger.debug(f"Estimated output tokens from content: {output_tokens}")

    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(input_tokens + output_tokens),
    }


def prepare_messages(
    system_prompt: str,
    user_prompt: str,
    image_bytes: Optional[bytes] = None,
    image_format: str = "png"
) -> List[BaseMessage]:
    """
    Prepare LangChain messages for LLM invocation.

    Args:
        system_prompt: System context.
        user_prompt: User instruction.
        image_bytes: Optional image data for multi-modal calls.
        image_format: Image format (default: png).

    Returns:
        List of [SystemMessage, HumanMessage].
    """
    if image_bytes:
        # Multi-modal content
        user_content = [
            {"type": "text", "text": user_prompt},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": f"image/{image_format}",
                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                },
            },
        ]
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
    
    # Text-only content
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]


def parse_response_content(response_content: Any) -> str:
    """
    Parse response content into a single string.
    
    Handles direct strings or list of content blocks.
    """
    if isinstance(response_content, list):
        total_think = []
        total_text = []
        
        for block in response_content:
            if isinstance(block, dict):
                block_type = block.get("type", "")
                
                # Extract reasoning/thinking
                if block_type == "reasoning_content" or "reasoning_content" in block:
                    reasoning_data = block.get("reasoning_content", {})
                    if isinstance(reasoning_data, dict):
                        total_think.append(reasoning_data.get("text", ""))
                    elif isinstance(reasoning_data, str):
                        total_think.append(reasoning_data)
                
                # Extract main text
                elif block_type == "text" or "text" in block:
                    total_text.append(block.get("text", ""))
                
                # Other data
                elif "json" in block:
                    total_text.append(str(block["json"]))
            
            elif isinstance(block, str):
                total_text.append(block)

        think_content = "".join(total_think).strip()
        main_content = "".join(total_text).strip()

        # Resilient Rescue Logic: If prompt is trapped in thinking block
        if "<prompt>" in think_content and "<prompt>" not in main_content:
            import re
            prompt_match = re.search(r'<prompt>(.*?)</prompt>', think_content, re.DOTALL | re.IGNORECASE)
            if prompt_match:
                main_content = prompt_match.group(0).strip()
                think_content = think_content.replace(main_content, "").strip()

        # DETECT PURE JSON - Skip structural wrapper for ad styling (User Request 03:34)
        is_direct_json = (main_content.startswith('{') and main_content.endswith('}')) or \
                        (main_content.startswith('[') and main_content.endswith(']'))
        
        if is_direct_json and not think_content:
            return main_content

        # Reconstruct final separated response (Original structural behavior)
        output_parts = []
        if think_content:
            output_parts.append(f"### 🧠 Reasoning Logic\n<think>\n{think_content}\n</think>\n\n---\n\n")
        
        if main_content:
            output_parts.append("### 🎨 Final Enhanced Prompt\n")
            output_parts.append(main_content)
        elif think_content:
            output_parts.append("### 🎨 Final Enhanced Prompt\n")

        return "".join(output_parts)

    return str(response_content)
