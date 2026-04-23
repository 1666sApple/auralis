"""AWS Bedrock client using LangChain for LLM and native SDK for embeddings.

This is the unified client that all services use. LLM calls now go through
LangChain (via LangChainLLM) while embeddings use the separate BedrockEmbeddingClient.
"""

import numpy as np
from typing import List, Dict, Tuple, Generator, Optional
from langchain_aws import ChatBedrockConverse

from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger
from src.generator.bedrock.embedding_client import BedrockEmbeddingClient

logger = get_logger(__name__)


class BedrockClient:
    """Client for AWS Bedrock services.
    
    Acts as a facade delegating:
    - LLM operations -> src.generator.intelligence.langchain_llm.LangChainLLM
    - Embeddings -> src.generator.bedrock.embedding_client.BedrockEmbeddingClient
    """

    def __init__(
        self,
        aws_access_key: str = None,
        aws_secret_key: str = None,
        region_name: str = None,
        token_tracker=None,
    ):
        """Initialize Bedrock client.

        Args:
            aws_access_key: AWS access key ID.
            aws_secret_key: AWS secret access key.
            region_name: AWS region name.
            token_tracker: Optional TokenTracker instance.
        """
        try:
            # Initialize Embedding Client
            self.embedding_client = BedrockEmbeddingClient(
                region_name=region_name,
            )

            # Initialize Core LLM Client (Singleton)
            from src.generator.intelligence.langchain_llm import get_langchain_llm
            self.llm_client = get_langchain_llm(token_tracker=token_tracker)
            
            # Expose properties for backward compatibility
            self.embedding_model_id = self.embedding_client.embedding_model_id
            self.llm_model_id = self.llm_client.model_id
            self.region = self.llm_client.region_name
            self.default_temperature = self.llm_client.default_temperature
            self.default_max_tokens = self.llm_client.default_max_tokens
            logger.info("BedrockClient initialized (Facade -> LangChainLLM + EmbeddingClient)")

            self.token_tracker = token_tracker
            
        except Exception as e:
            logger.error(f"Failed to initialize BedrockClient: {e}", exc_info=True)
            raise

    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for a single text."""
        return self.embedding_client.get_embedding(text)

    def get_embeddings_batch(
        self, texts: List[str], batch_size: int = None
    ) -> np.ndarray:
        """Get embeddings for multiple texts."""
        return self.embedding_client.get_embeddings_batch(texts, batch_size)

    def invoke_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = None,
        max_tokens: int = None,
        track_as: str = None,
        track_metadata: Dict = None,
        model_id: str = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Invoke LLM via LangChainLLM delegate."""
        return self.llm_client.invoke_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            track_as=track_as,
            track_metadata=track_metadata,
            model_id=model_id
        )

    def invoke_llm_with_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes_list: list[bytes],
        media_type: str,
        temperature: float = None,
        max_tokens: int = None,
        track_as: str = None,
        track_metadata: Dict = None,
        model_id: str = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Invoke Vision LLM via LangChainLLM delegate."""
        # Extract format from media_type (e.g. "image/png" -> "png")
        image_format = media_type.split("/")[-1] if "/" in media_type else "png"
        
        return self.llm_client.invoke_vision_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_bytes=image_bytes_list[0],
            image_format=image_format,
            temperature=temperature,
            max_tokens=max_tokens,
            track_as=track_as,
        )

    def invoke_llm_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = None,
        max_tokens: int = None,
        model_id: str = None,
        track_as: str = "generation_stream",
    ) -> Generator:
        """Invoke LLM stream via LangChainLLM delegate."""
        return self.llm_client.invoke_llm_stream(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def ainvoke_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = None,
        max_tokens: int = None,
        track_as: str = None,
        track_metadata: Dict = None,
        model_id: str = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Async version of invoke_llm."""
        return await self.llm_client.ainvoke_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            track_as=track_as,
            track_metadata=track_metadata,
            model_id=model_id
        )


    async def invoke_llm_astream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = None,
        max_tokens: int = None,
        model_id: str = None,
        track_as: str = "generation_stream",
    ):
        """Invoke Async LLM stream via LangChainLLM delegate."""
        async for chunk in self.llm_client.astream_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk

    @staticmethod
    def get_available_models(region: str = "us-east-1") -> dict:
        """Get available Claude models."""
        return {
            "claude-3.5-sonnet-v2": f"{region}.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "claude-3.5-sonnet-v1": f"{region}.anthropic.claude-3-5-sonnet-20240620-v1:0",
            "claude-3-haiku": f"{region}.anthropic.claude-3-haiku-20240307-v1:0",
            "claude-3-sonnet-legacy": "anthropic.claude-3-sonnet-20240229-v1:0",
        }
