"""Registry for reasoning strategies."""

from typing import Dict, Type
from src.generator.prompts.reasoner.strategies.base_strategy import BaseReasoningStrategy
from src.generator.prompts.reasoner.strategies.tree_of_thought import TreeOfThoughtStrategy
from src.generator.prompts.reasoner.strategies.chain_of_thought import ChainOfThoughtStrategy
from src.generator.prompts.reasoner.strategies.multipath import MultipathStrategy
from src.generator.prompts.reasoner.strategies.fact_lookup import FactLookupStrategy
from src.generator.prompts.reasoner.strategies.graph_of_thought import GraphOfThoughtStrategy
from src.generator.prompts.reasoner.strategies.structured_analysis import (
    StructuredAnalysisStrategy,
)
from src.generator.prompts.reasoner.strategies.self_consistency import SelfConsistencyStrategy


class StrategyRegistry:
    """Manages and provides reasoning strategy instances."""

    def __init__(self, bedrock_client, prompt_loader):
        self.bedrock_client = bedrock_client
        self.prompt_loader = prompt_loader
        self._strategies: Dict[str, BaseReasoningStrategy] = {}
        self._initialize_strategies()

    def _initialize_strategies(self):
        """Initialize all available strategies."""
        self._strategies["tree_of_thought"] = TreeOfThoughtStrategy(
            self.bedrock_client, self.prompt_loader
        )
        self._strategies["chain_of_thought"] = ChainOfThoughtStrategy(
            self.bedrock_client, self.prompt_loader
        )
        self._strategies["multipath"] = MultipathStrategy(
            self.bedrock_client, self.prompt_loader
        )
        self._strategies["fact_lookup"] = FactLookupStrategy(
            self.bedrock_client, self.prompt_loader
        )
        self._strategies["graph_of_thought"] = GraphOfThoughtStrategy(
            self.bedrock_client, self.prompt_loader
        )
        self._strategies["structured_analysis"] = StructuredAnalysisStrategy(
            self.bedrock_client, self.prompt_loader
        )
        self._strategies["self_consistency"] = SelfConsistencyStrategy(
            self.bedrock_client, self.prompt_loader
        )

    def get_strategy(self, name: str) -> BaseReasoningStrategy:
        """Get a strategy instance by name."""
        return self._strategies.get(name)
