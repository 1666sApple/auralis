"""Strategy for direct, FAQ, and definition lookups."""

from typing import Tuple, Any
from src.generator.prompts.reasoner.strategies.base_strategy import BaseReasoningStrategy
from src.generator.prompts.reasoner.models import ReasoningTrace
from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class FactLookupStrategy(BaseReasoningStrategy):
    """Applies direct fact-based lookup reasoning."""

    def apply(
        self, query: str, context: str, mode: str, **kwargs
    ) -> Tuple[str, ReasoningTrace]:
        lookup_type = kwargs.get("lookup_type", "direct")
        logger.info(f"Applying Fact Lookup strategy: {lookup_type}")

        if lookup_type == "faq":
            return self._apply_faq(query, context, mode)
        elif lookup_type == "definition":
            return self._apply_definition(query, context, mode)
        else:
            return self._apply_direct(query, context, mode)

    def _apply_direct(
        self, query: str, context: str, mode: str
    ) -> Tuple[str, ReasoningTrace]:
        system_prompt = self.prompt_loader.get_system_prompt("concise")
        base_instructions = self.prompt_loader.get_instructions()

        lookup_prompt = self.prompt_loader.get_reasoning_user_prompt(
            strategy="direct_lookup",
            query=query,
            context=context,
            base_instructions=base_instructions,
        )

        response, _ = self.bedrock_client.invoke_llm(
            system_prompt=system_prompt,
            user_prompt=lookup_prompt,
            temperature=0.1,
            max_tokens=768,
            track_as="generation",
            track_metadata={"query": query[:50]},
            model_id=settings.LLM_MODEL_ID,
        )

        clean_response = self._clean_reasoning_output(response)
        trace = ReasoningTrace(
            method="Direct Lookup",
            branches=["direct_answer"],
            conclusions=[{"type": "lookup", "status": "complete"}],
            confidence=0.90,
            citations=self._extract_citations(clean_response),
        )
        return clean_response, trace

    def _apply_faq(
        self, query: str, context: str, mode: str
    ) -> Tuple[str, ReasoningTrace]:
        system_prompt = self.prompt_loader.get_system_prompt("concise")
        faq_prompt = self.prompt_loader.get_reasoning_user_prompt(
            strategy="faq_lookup",
            query=query,
            context=context,
        )

        response, _ = self.bedrock_client.invoke_llm(
            system_prompt=system_prompt,
            user_prompt=faq_prompt,
            temperature=0.1,
            max_tokens=150,
            track_as="generation",
            track_metadata={"query": query[:50], "type": "faq"},
            model_id=settings.LLM_MODEL_ID,
        )

        clean_response = self._clean_reasoning_output(response)
        trace = ReasoningTrace(
            method="FAQ Lookup",
            branches=["faq_answer"],
            conclusions=[{"type": "faq", "status": "complete"}],
            confidence=0.92,
            citations=self._extract_citations(clean_response),
        )
        return clean_response, trace

    def _apply_definition(
        self, query: str, context: str, mode: str
    ) -> Tuple[str, ReasoningTrace]:
        system_prompt = self.prompt_loader.get_system_prompt("conversational")
        definition_prompt = self.prompt_loader.get_reasoning_user_prompt(
            strategy="definition",
            query=query,
            context=context,
        )

        response, _ = self.bedrock_client.invoke_llm(
            system_prompt=system_prompt,
            user_prompt=definition_prompt,
            temperature=0.2,
            max_tokens=768,
            track_as="generation",
            track_metadata={"query": query[:50]},
            model_id=settings.LLM_MODEL_ID,
        )

        clean_response = self._clean_reasoning_output(response)
        trace = ReasoningTrace(
            method="Definition Clarification (Direct)",
            branches=["structured_definition"],
            conclusions=[{"type": "definition", "status": "complete"}],
            confidence=0.92,
            citations=self._extract_citations(clean_response),
        )
        return clean_response, trace
