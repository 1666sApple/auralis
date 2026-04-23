"""Graph of Thought reasoning strategy."""

from typing import Tuple, Any
from src.generator.prompts.reasoner.strategies.base_strategy import BaseReasoningStrategy
from src.generator.prompts.reasoner.models import ReasoningTrace
from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class GraphOfThoughtStrategy(BaseReasoningStrategy):
    """Applies Graph of Thought reasoning."""

    def apply(
        self, query: str, context: str, mode: str, **kwargs
    ) -> Tuple[str, ReasoningTrace]:
        logger.info("Applying Graph of Thought reasoning")

        system_prompt = self.prompt_loader.get_system_prompt("conversational")
        base_instructions = self.prompt_loader.get_instructions()

        got_prompt = self.prompt_loader.get_reasoning_user_prompt(
            strategy="graph_of_thought",
            query=query,
            context=context,
            base_instructions=base_instructions,
        )

        try:
            response, _ = self.bedrock_client.invoke_llm(
                system_prompt=system_prompt,
                user_prompt=got_prompt,
                temperature=0.3,
                track_as="generation",
                track_metadata={"query": query[:50]},
                model_id=settings.LLM_MODEL_ID,
            )

            clean_response = self._clean_reasoning_output(response)

            trace = ReasoningTrace(
                method="Graph of Thought",
                branches=["policy_interaction"],
                conclusions=[{"type": "graph_analysis", "status": "complete"}],
                confidence=0.87,
                citations=self._extract_citations(clean_response),
            )

            return clean_response, trace

        except Exception as e:
            logger.error(f"Graph of Thought strategy failed: {e}", exc_info=True)
            raise e
