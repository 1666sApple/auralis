"""Structured analysis reasoning strategy."""

from typing import Tuple, Any
from src.generator.prompts.reasoner.strategies.base_strategy import BaseReasoningStrategy
from src.generator.prompts.reasoner.models import ReasoningTrace
from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class StructuredAnalysisStrategy(BaseReasoningStrategy):
    """Applies Structured Analysis reasoning."""

    def apply(
        self, query: str, context: str, mode: str, **kwargs
    ) -> Tuple[str, ReasoningTrace]:
        logger.info("Applying Structured Analysis reasoning")

        system_prompt = self.prompt_loader.get_system_prompt("analytical")
        base_instructions = self.prompt_loader.get_instructions()

        comparison_prompt = self.prompt_loader.get_reasoning_user_prompt(
            strategy="structured_analysis",
            query=query,
            context=context,
            base_instructions=base_instructions,
        )

        try:
            response, _ = self.bedrock_client.invoke_llm(
                system_prompt=system_prompt,
                user_prompt=comparison_prompt,
                temperature=0.2,
                track_as="generation",
                track_metadata={"query": query[:50]},
                model_id=settings.LLM_MODEL_ID,
            )

            clean_response = self._clean_reasoning_output(response)

            trace = ReasoningTrace(
                method="Structured Analysis",
                branches=["comparative_analysis"],
                conclusions=[{"type": "comparison", "status": "complete"}],
                confidence=0.89,
                citations=self._extract_citations(clean_response),
            )

            return clean_response, trace

        except Exception as e:
            logger.error(f"Structured Analysis strategy failed: {e}", exc_info=True)
            raise e
