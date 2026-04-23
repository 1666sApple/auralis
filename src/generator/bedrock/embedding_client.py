import os
import numpy as np
from typing import List, Optional
from src.shared.config.settings import settings
from src.shared.utils.auth_helper import get_boto3_client
from src.generator.bedrock.bedrock_embeddings import BedrockEmbeddings
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class BedrockEmbeddingClient:
    """Client for AWS Bedrock embedding operations."""

    def __init__(self, region_name: str = None):
        """Initialize Bedrock Embedding client.

        Args:
            region_name: AWS region name.
        """
        try:
            # Region priority: argument > AWS_REGION_EMBEDDING > AWS_REGION
            self.region = (
                region_name
                or settings.AWS_REGION_EMBEDDING
                or settings.AWS_REGION
            )
            self.embedding_model_id = settings.EMBEDDING_MODEL_ID

            self.bedrock_runtime = get_boto3_client(
                service_name="bedrock-runtime",
                region_name=self.region,
                max_attempts=3,
                read_timeout=60
            )

            # Initialize embeddings service
            self._embeddings = BedrockEmbeddings(
                self.bedrock_runtime, self.embedding_model_id
            )

            logger.info(
                f"BedrockEmbeddingClient initialized - Model: {self.embedding_model_id}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize BedrockEmbeddingClient: {e}", exc_info=True)
            raise

    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for a single text.

        Args:
            text: Input text string.

        Returns:
            np.ndarray: Normalized embedding vector.
        """
        return self._embeddings.get_embedding(text)

    def get_embeddings_batch(
        self, texts: List[str], batch_size: int = None
    ) -> np.ndarray:
        """Get embeddings for multiple texts.

        Args:
            texts: List of input text strings.
            batch_size: Batch size for processing.

        Returns:
            np.ndarray: Array of normalized embeddings.
        """
        return self._embeddings.get_embeddings_batch(texts, batch_size)