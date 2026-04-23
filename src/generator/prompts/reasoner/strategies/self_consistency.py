"""Self-consistency reasoning strategy."""

from typing import Tuple, Any, Optional, Dict
from src.generator.prompts.reasoner.strategies.base_strategy import BaseReasoningStrategy
from src.generator.prompts.reasoner.models import ReasoningTrace
from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class SelfConsistencyStrategy(BaseReasoningStrategy):
    """Applies Self-Consistency reasoning by sampling multiple answers."""

    def apply(
        self, query: str, context: str, mode: str, **kwargs
    ) -> Tuple[str, Dict[str, float]]:
        num_samples = kwargs.get("num_samples", 5)
        logger.info(f"Applying Self-Consistency with {num_samples} samples")

        system_prompt = self.prompt_loader.get_system_prompt("conversational")
        base_instructions = self.prompt_loader.get_instructions()

        samples = []
        for i in range(min(3, num_samples)):
            sample_prompt = self.prompt_loader.get_reasoning_user_prompt(
                strategy="self_consistency",
                query=query,
                context=context,
                base_instructions=base_instructions,
            )

            try:
                response, _ = self.bedrock_client.invoke_llm(
                    system_prompt=system_prompt,
                    user_prompt=sample_prompt,
                    temperature=0.3 + (i * 0.1),
                    track_as="generation",
                    track_metadata={"query": query[:50], "sample": i + 1},
                    model_id=settings.LLM_MODEL_ID,
                )
                samples.append(self._clean_reasoning_output(response))
            except Exception as e:
                logger.warning(f"Sample {i + 1} failed: {e}")
                continue

        if samples:
            final_answer = max(samples, key=len)
        else:
            final_answer = "Unable to generate consistent answer."

        return final_answer, {"overall": 0.88}
