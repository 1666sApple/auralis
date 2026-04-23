"""Multipath reasoning strategy."""

import re
from typing import Tuple, Any, Optional
from src.generator.prompts.reasoner.strategies.base_strategy import BaseReasoningStrategy
from src.generator.prompts.reasoner.models import ReasoningTrace
from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class MultipathStrategy(BaseReasoningStrategy):
    """Applies Multipath reasoning with multiple thought paths."""

    def apply(
        self, query: str, context: str, mode: str, **kwargs
    ) -> Tuple[str, ReasoningTrace]:
        num_paths = kwargs.get("num_paths")
        complexity_level = kwargs.get("complexity_level", "complex")
        max_context_chars = kwargs.get("max_context_chars", 4000)
        max_output_tokens = kwargs.get("max_output_tokens", 512)

        if complexity_level in ["simple", "moderate"]:
            logger.info(f"Skipping multipath for {complexity_level} query")
            # This should ideally be handled by the caller or redirected
            raise ValueError(
                f"Multipath not recommended for {complexity_level} complexity"
            )

        if num_paths is None:
            num_paths = 5 if complexity_level == "extra_complex" else 3

        if len(context) > max_context_chars:
            logger.warning(
                f"Context truncated from {len(context)} to {max_context_chars} chars"
            )
            context = (
                context[:max_context_chars]
                + "\n\n[Context truncated to fit token limit]"
            )

        logger.info(
            f"Applying Multipath Reasoning - Complexity: {complexity_level}, Paths: {num_paths}"
        )

        system_prompt = self.prompt_loader.get_system_prompt("conversational")
        base_instructions = self.prompt_loader.get_instructions()

        paths = []
        for i in range(num_paths):
            path_prompt = self.prompt_loader.get_reasoning_user_prompt(
                strategy="multipath",
                query=query,
                context=context,
                base_instructions=base_instructions,
                path_focus=self._get_path_focus(i),
            )

            try:
                response, _ = self.bedrock_client.invoke_llm(
                    system_prompt=system_prompt,
                    user_prompt=path_prompt,
                    temperature=0.2 + (i * 0.1),
                    max_tokens=max_output_tokens,
                    track_as="generation",
                    track_metadata={"query": query[:50], "path": i + 1},
                    model_id=settings.LLM_MODEL_ID,
                )
                paths.append(response)
            except Exception as e:
                logger.warning(f"Path {i + 1} failed: {e}")
                continue

        if not paths:
            raise Exception("All multipath reasoning paths failed.")

        best_response = max(paths, key=len)
        clean_response = self._clean_reasoning_output(best_response)

        trace = ReasoningTrace(
            method="Multipath Reasoning",
            branches=[f"path_{i + 1}" for i in range(len(paths))],
            conclusions=[
                {
                    "type": "convergent",
                    "paths_evaluated": len(paths),
                    "complexity": complexity_level,
                }
            ],
            confidence=0.86,
            citations=self._extract_citations(clean_response),
        )

        return clean_response, trace

    def _get_path_focus(self, path_index: int) -> str:
        focuses = [
            "eligibility criteria and requirements",
            "process and procedures",
            "exceptions and special cases",
            "timelines and deadlines",
            "related policies and interactions",
        ]
        return focuses[path_index % len(focuses)]
