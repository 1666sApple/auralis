"""Base class for all reasoning strategies."""

import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class BaseReasoningStrategy(ABC):
    """Abstract base class for reasoning strategies."""

    def __init__(self, bedrock_client, prompt_loader):
        self.bedrock_client = bedrock_client
        self.prompt_loader = prompt_loader

    @abstractmethod
    def apply(
        self, query: str, context: str, mode: str, **kwargs
    ) -> Tuple[str, Any]:  # Any will be ReasoningTrace
        """Apply the reasoning strategy."""
        pass

    def _clean_reasoning_output(self, response: str) -> str:
        """Clean reasoning output to remove JSON artifacts."""
        cleaned = re.sub(r"```json\s*\{.*?\}\s*```", "", response, flags=re.DOTALL)
        cleaned = re.sub(r"```\s*\{.*?\}\s*```", "", cleaned, flags=re.DOTALL)

        cleaned = re.sub(r'\{[\s\n]*"decomposition".*?\}', "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'\{[\s\n]*"branches".*?\}', "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'\{[\s\n]*"id":\s*"branch.*?\}', "", cleaned, flags=re.DOTALL)

        cleaned = re.sub(
            r"---+\s*##?\s*(Reasoning Trace|Analysis Details).*?(?=##|\Z)",
            "",
            cleaned,
            flags=re.DOTALL | re.MULTILINE,
        )

        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = cleaned.strip()

        return cleaned

    def _extract_citations(self, text: str) -> List[str]:
        """Extract citations in format [Source: X, Section: Y, Page: Z]."""
        pattern = r"\[Source:.*?(?:Section:.*?)?(?:Page:\s*\d+)?\]"
        citations = re.findall(pattern, text)
        return list(set(citations))
