"""Integration layer for advanced reasoning with existing RAG system."""

from typing import Dict, Optional, Any
from src.generator.prompts.reasoner.advanced_reasoner import AdvancedReasoner, ReasoningTrace
from src.services.query.query_strategy_graph import QueryStrategyGraph
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class ReasoningIntegrator:
    """Integrates LangGraph-based reasoning into RAG pipeline."""

    def __init__(
        self,
        bedrock_client,
        prompt_loader,
        query_preprocessor: Optional[Any] = None,
    ):
        """
        Initialize ReasoningIntegrator.

        Args:
            bedrock_client: BedrockClient instance.
            prompt_loader: PromptLoader instance.
            query_preprocessor: Deprecated (kept for compatibility).
        """
        self.strategy_graph = QueryStrategyGraph(bedrock_client, prompt_loader)
        self.prompt_loader = prompt_loader
        self.advanced_reasoner = AdvancedReasoner(bedrock_client, prompt_loader)

        config = prompt_loader.get_advanced_reasoning_config()
        self.min_context_length = config.get("min_context_length", 500)
        self.min_confidence_threshold = config.get("min_confidence_threshold", 0.85)
        self.complexity_threshold = config.get("complexity_threshold", 0.7)

        logger.info("ReasoningIntegrator initialized with QueryStrategyGraph")

    def should_apply_advanced_reasoning(
        self, query: str, context: str, routing_decision
    ) -> bool:
        """
        Determine if advanced reasoning should be applied.

        Args:
            query: User query.
            context: Retrieved context.
            routing_decision: RoutingDecision from query router.

        Returns:
            True if advanced reasoning should be applied.
        """
        if not routing_decision.requires_retrieval:
            logger.debug("Skipping advanced reasoning for non-retrieval query")
            return False

        skip_types = ["greeting", "chitchat", "feedback"]
        if routing_decision.route_type in skip_types:
            logger.debug(
                f"Skipping advanced reasoning for {routing_decision.route_type}"
            )
            return False

        has_sufficient_context = len(context) >= self.min_context_length

        should_apply = (
            routing_decision.route_type in ["situational", "hr_query"]
            and has_sufficient_context
        )

        if should_apply:
            logger.info(
                f"Advanced reasoning will be applied - "
                f"Context length: {len(context)}, Type: {routing_decision.route_type}"
            )
        else:
            logger.debug("Standard reasoning sufficient for this query")

        return should_apply

    def process_with_reasoning(
        self, query: str, context: str, mode: str, routing_decision
    ) -> Dict[str, Any]:
        """
        Enhance answer generation with LangGraph-based reasoning.

        Args:
            query: User query.
            context: Retrieved context.
            mode: Response mode.
            routing_decision: RoutingDecision from query router.

        Returns:
            Dict with reasoned_answer and reasoning_metadata.
        """
        try:
            logger.info(f"Enhancing with LangGraph reasoning - Mode: {mode}")

            result = self.strategy_graph.execute(
                query=query,
                context=context,
                mode=mode,
                conversation_history=None,
            )

            return {
                "reasoned_answer": result["response"],
                "reasoning_metadata": {
                    "method": result.get("reasoning_method", "unknown"),
                    "query_type": result.get("strategy_type", "unknown"),
                    "confidence": result.get("confidence", 0.0),
                    "strategy_graph_used": True,
                },
                "reasoning_trace": result.get("reasoning_trace"),
            }

        except Exception as e:
            logger.error(f"LangGraph reasoning enhancement failed: {e}", exc_info=True)
            return {
                "reasoned_answer": None,
                "reasoning_metadata": {
                    "method": "fallback",
                    "error": str(e),
                    "strategy_graph_used": False,
                },
                "reasoning_trace": None,
            }

    def apply_self_consistency_check(
        self, query: str, context: str, mode: str, num_samples: int = 5
    ) -> Dict[str, Any]:
        """
        Apply self-consistency check for critical queries.

        Args:
            query: User query.
            context: Retrieved context.
            mode: Response mode.
            num_samples: Number of samples for consistency check.

        Returns:
            Dict with verified_answer and confidence scores.
        """
        try:
            logger.info(f"Applying self-consistency check with {num_samples} samples")

            verified_answer, claim_confidence = (
                self.advanced_reasoner.apply_self_consistency(
                    query=query, context=context, mode=mode, num_samples=num_samples
                )
            )

            return {
                "verified_answer": verified_answer,
                "claim_confidence": claim_confidence,
                "verification_status": "passed"
                if min(claim_confidence.values()) >= 0.6
                else "low_confidence",
            }

        except Exception as e:
            logger.error(f"Self-consistency check failed: {e}", exc_info=True)
            return {
                "verified_answer": None,
                "claim_confidence": {},
                "verification_status": "error",
                "error": str(e),
            }

    def get_reasoning_config(self) -> Dict[str, Any]:
        """
        Get current reasoning configuration.

        Returns:
            Dict with configuration parameters.
        """
        return {
            "default_num_paths": self.advanced_reasoner.default_num_paths,
            "default_branches_per_tot": self.advanced_reasoner.default_branches_per_tot,
            "default_consistency_samples": self.advanced_reasoner.default_consistency_samples,
            "min_confidence_threshold": self.advanced_reasoner.min_confidence_threshold,
            "complexity_threshold": self.complexity_threshold,
            "min_context_length": self.min_context_length,
        }

    def update_reasoning_config(self, config: Dict[str, Any]) -> None:
        """
        Update reasoning configuration.

        Args:
            config: Dict with configuration parameters to update.
        """
        if "default_num_paths" in config:
            self.advanced_reasoner.default_num_paths = config["default_num_paths"]

        if "default_branches_per_tot" in config:
            self.advanced_reasoner.default_branches_per_tot = config[
                "default_branches_per_tot"
            ]

        if "default_consistency_samples" in config:
            self.advanced_reasoner.default_consistency_samples = config[
                "default_consistency_samples"
            ]

        if "min_confidence_threshold" in config:
            self.advanced_reasoner.min_confidence_threshold = config[
                "min_confidence_threshold"
            ]

        if "complexity_threshold" in config:
            self.complexity_threshold = config["complexity_threshold"]

        if "min_context_length" in config:
            self.min_context_length = config["min_context_length"]

        logger.info(f"Reasoning configuration updated: {config}")


def get_reasoning_integrator(
    bedrock_client=None, prompt_loader=None, query_preprocessor=None
) -> ReasoningIntegrator:
    """
    Get a ReasoningIntegrator instance.

    Args:
        bedrock_client: BedrockClient instance (required).
        prompt_loader: PromptLoader instance (required).
        query_preprocessor: Optional QueryPreprocessor instance.

    Returns:
        ReasoningIntegrator instance.

    Raises:
        ValueError: If bedrock_client or prompt_loader not provided.
    """
    if bedrock_client is None or prompt_loader is None:
        raise ValueError("bedrock_client and prompt_loader required for initialization")

    return ReasoningIntegrator(
        bedrock_client=bedrock_client,
        prompt_loader=prompt_loader,
        query_preprocessor=query_preprocessor,
    )
