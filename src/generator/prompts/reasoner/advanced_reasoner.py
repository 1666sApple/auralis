"""Advanced reasoning engine implementing Tree of Thought, Chain of Thought, Multipath Reasoning, etc."""

import re
from typing import List, Dict, Optional, Tuple, Any
from src.shared.logger.logger_config import get_logger
from src.shared.config.settings import settings
from src.generator.prompts.reasoner.models import ReasoningTrace, ThoughtBranch
from src.generator.prompts.reasoner.strategies.strategy_registry import StrategyRegistry

logger = get_logger(__name__)


class AdvancedReasoner:
    """Implements state-of-the-art reasoning strategies using the Strategy pattern."""

    def __init__(self, bedrock_client, prompt_loader):
        """
        Initialize AdvancedReasoner.

        Args:
            bedrock_client: BedrockClient instance.
            prompt_loader: PromptLoader instance.
        """
        self.bedrock_client = bedrock_client
        self.prompt_loader = prompt_loader
        self.registry = StrategyRegistry(bedrock_client, prompt_loader)

        config = self.prompt_loader.get_advanced_reasoning_config()
        self.default_num_paths = config.get("default_num_paths", 3)
        self.default_branches_per_tot = config.get("default_branches_per_tot", 4)
        self.default_consistency_samples = config.get("default_consistency_samples", 5)
        self.min_confidence_threshold = config.get("min_confidence_threshold", 0.85)

        self.max_context_chars = 4000
        self.max_output_tokens = 512

        logger.info("AdvancedReasoner initialized - Modular architecture active")

    def apply_reasoning(
        self, query: str, context: str, query_type: str, mode: str = "default"
    ) -> Tuple[str, ReasoningTrace]:
        """
        Apply appropriate reasoning strategy based on query type.

        Args:
            query: User query.
            context: Retrieved document context.
            query_type: Strategy type from QueryClassifier.
            mode: Response mode.

        Returns:
            Tuple of (improved_prompt, reasoning_trace).
        """
        logger.info(f"Applying reasoning strategy for query type: {query_type}")

        strategy_mapping = {
            "comprehensive_explanation": "tree_of_thought",
            "step_by_step_process": "chain_of_thought",
            "comparison_analysis": "structured_analysis",
            "contextual_scenario": "graph_of_thought",
            "problem_diagnosis": "multipath",
            "temporal_constraint": "chain_of_thought",
            "quantitative_verification": "multipath",
            "eligibility_assessment": "structured_analysis",
            "definition_clarification": "fact_lookup",
            "specific_lookup": "fact_lookup",
            "faq_lookup": "fact_lookup",
            "broad": "tree_of_thought",
            "procedural": "chain_of_thought",
            "comparative": "structured_analysis",
            "situational": "graph_of_thought",
        }

        strategy_name = strategy_mapping.get(query_type, "multipath")
        strategy = self.registry.get_strategy(strategy_name)

        if not strategy:
            logger.warning(f"Strategy {strategy_name} not found, falling back")
            return self._fallback_reasoning(query, context, mode)

        # Handle special kwargs for strategies
        kwargs = {}
        if strategy_name == "fact_lookup":
            if "faq" in query_type:
                kwargs["lookup_type"] = "faq"
            elif "definition" in query_type:
                kwargs["lookup_type"] = "definition"
            else:
                kwargs["lookup_type"] = "direct"
        elif strategy_name == "multipath":
            kwargs["num_paths"] = self.default_num_paths
            kwargs["max_context_chars"] = self.max_context_chars
            kwargs["max_output_tokens"] = self.max_output_tokens

        try:
            return strategy.apply(query, context, mode, **kwargs)
        except Exception as e:
            logger.error(
                f"Reasoning strategy {strategy_name} failed: {e}", exc_info=True
            )
            return self._fallback_reasoning(query, context, mode)

    def apply_self_consistency(
        self, query: str, context: str, mode: str, num_samples: Optional[int] = None
    ) -> Tuple[str, Dict[str, float]]:
        """Apply Self-Consistency to verify factual claims."""
        strategy = self.registry.get_strategy("self_consistency")
        return strategy.apply(
            query,
            context,
            mode,
            num_samples=num_samples or self.default_consistency_samples,
        )

    def format_reasoning_trace_appendix(self, trace: ReasoningTrace, mode: str) -> str:
        """Format reasoning trace as appendix - ONLY for detailed mode."""
        if mode != "detailed":
            return ""

        if trace.confidence >= self.min_confidence_threshold:
            return ""

        appendix = f"""

---
## Analysis Details

**Reasoning Method**: {trace.method}  
**Confidence Level**: {trace.confidence:.0%}

**Note**: This answer was generated using advanced reasoning techniques to ensure accuracy. The confidence level indicates the degree of certainty based on the available documentation."""

        if trace.confidence < 0.7:
            appendix += """

**⚠️ Lower Confidence Notice**: Please verify critical details or request clarification if needed, as the available documentation may have limited information on this specific aspect.
"""

        return appendix

    def _fallback_reasoning(
        self, query: str, context: str, mode: str
    ) -> Tuple[str, ReasoningTrace]:
        """Fallback when advanced reasoning fails."""
        logger.warning("Using fallback reasoning")

        system_prompt = self.prompt_loader.get_system_prompt("conversational")
        base_instructions = self.prompt_loader.get_instructions()

        fallback_prompt = f"""Answer this HR policy question.

**Query:** {query}

**Context:**
{context}

{base_instructions}

Provide a concise answer with brief citations (Document p.X). Stop when done."""

        try:
            response, _ = self.bedrock_client.invoke_llm(
                system_prompt=system_prompt,
                user_prompt=fallback_prompt,
                temperature=0.3,
                track_as="generation",
                track_metadata={"query": query[:50]},
                model_id=settings.LLM_MODEL_ID,
            )
            clean_response = self._clean_reasoning_output(response)
        except Exception:
            clean_response = (
                "I'm having trouble generating an answer right now. "
                "Please try again or contact HR directly for assistance."
            )

        trace = ReasoningTrace(
            method="Fallback",
            branches=["fallback"],
            conclusions=[{"type": "fallback"}],
            confidence=0.75,
            citations=self._extract_citations_from_text(clean_response),
        )

        return clean_response, trace

    def _clean_reasoning_output(self, response: str) -> str:
        """Utility method preserved for fallback and internal use."""
        cleaned = re.sub(r"```json\s*\{.*?\}\s*```", "", response, flags=re.DOTALL)
        cleaned = re.sub(r"```\s*\{.*?\}\s*```", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _extract_citations_from_text(self, text: str) -> List[str]:
        """Utility method preserved for fallback and internal use."""
        pattern = r"\[Source:.*?(?:Section:.*?)?(?:Page:\s*\d+)?\]"
        citations = re.findall(pattern, text)
        return list(set(citations))
