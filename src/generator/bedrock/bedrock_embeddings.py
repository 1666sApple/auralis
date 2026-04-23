"""AWS Bedrock embeddings service.

Handles embedding generation for text using Bedrock models.
"""

import json
import numpy as np
from typing import List
from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class BedrockEmbeddings:
    """Handles embedding generation using AWS Bedrock."""

    def __init__(self, bedrock_runtime, embedding_model_id: str):
        """Initialize embeddings service.

        Args:
            bedrock_runtime: Boto3 bedrock-runtime client.
            embedding_model_id: Model ID for embeddings (e.g., amazon.titan-embed-text-v1).
        """
        self.bedrock_runtime = bedrock_runtime
        self.embedding_model_id = embedding_model_id

    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for a single text.

        Args:
            text: Input text string.

        Returns:
            np.ndarray: Normalized embedding vector.
        """
        try:
            body = json.dumps({"inputText": text})

            response = self.bedrock_runtime.invoke_model(
                modelId=self.embedding_model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            embedding = np.array(response_body["embedding"], dtype="float32")

            # Normalize for cosine similarity
            embedding = embedding / np.linalg.norm(embedding)

            logger.debug(f"Generated embedding for text of length {len(text)}")
            return embedding
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}", exc_info=True)
            raise

    def get_embeddings_batch(
        self, texts: List[str], batch_size: int = None
    ) -> np.ndarray:
        """Get embeddings for multiple texts.

        Args:
            texts: List of input text strings.
            batch_size: Batch size for processing. Defaults to settings.EMBEDDING_BATCH_SIZE.

        Returns:
            np.ndarray: Array of normalized embeddings.
        """
        batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        embeddings = []
        total = len(texts)

        logger.info(f"Starting batch embedding generation for {total} texts")

        for i in range(0, total, batch_size):
            batch = texts[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            logger.info(f"Processing embedding batch {batch_num}/{total_batches}...")

            for text in batch:
                emb = self.get_embedding(text)
                embeddings.append(emb)

        result = np.array(embeddings, dtype="float32")
        logger.info(f"Batch embedding completed - Shape: {result.shape}")
        return result
