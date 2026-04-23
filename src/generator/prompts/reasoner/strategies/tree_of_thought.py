"""Tree of Thoughts reasoning strategy."""

from typing import Tuple, Any
from src.generator.prompts.reasoner.strategies.base_strategy import BaseReasoningStrategy
from src.generator.prompts.reasoner.models import ReasoningTrace
from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class TreeOfThoughtStrategy(BaseReasoningStrategy):
    """Applies Tree of Thoughts reasoning."""

    def apply(
        self, query: str, context: str, mode: str, **kwargs
    ) -> Tuple[str, ReasoningTrace]:
        logger.info("Applying Tree of Thoughts reasoning")

        max_tokens = self.prompt_loader.get_token_budget("reasoning", "extra_complex")
        system_prompt = self.prompt_loader.get_system_prompt("conversational")
        base_instructions = self.prompt_loader.get_instructions()

        tot_prompt = self.prompt_loader.get_reasoning_user_prompt(
            strategy="tree_of_thoughts",
            query=query,
            context=context,
            base_instructions=base_instructions,
        )

        try:
            response, _ = self.bedrock_client.invoke_llm(
                system_prompt=system_prompt,
                user_prompt=tot_prompt,
                temperature=0.3,
                max_tokens=max_tokens,
                track_as="generation",
                track_metadata={"query": query[:50]},
                model_id=settings.LLM_MODEL_ID,
            )

            clean_response = self._clean_reasoning_output(response)

            trace = ReasoningTrace(
                method="Tree of Thoughts",
                branches=["comprehensive_analysis"],
                conclusions=[{"type": "synthesized", "status": "complete"}],
                confidence=0.88,
                citations=self._extract_citations(clean_response),
            )

            return clean_response, trace

        except Exception as e:
            logger.error(f"Tree of Thoughts strategy failed: {e}", exc_info=True)
            raise e
