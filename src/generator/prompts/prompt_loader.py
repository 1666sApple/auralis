"""Unified PromptLoader acting as a facade for the modular prompt system."""

from pathlib import Path
from typing import Dict, Any, Optional
from src.shared.logger.logger_config import get_logger

# Import specialized loaders
from src.generator.prompts.loaders.schema_loader import SchemaLoader
from src.generator.prompts.loaders.image_prompt_loader import ImagePromptLoader

logger = get_logger(__name__)


class PromptLoader:
    """
    Unified facade for modular prompt management.
    Provides a consistent API while delegating to domain-specific loaders.
    """

    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize the modular prompt system.

        Args:
            template_dir: Optional path to directory containing XML templates.
        """
        if template_dir is None:
            # Default to templates directory relative to this file
            self.template_dir = Path(__file__).parent / "templates"
        else:
            self.template_dir = Path(template_dir)

        # Initialize schema and Image parsing loaders
        # Defaulting json schemas to the parent directory of templates
        self.schemas = SchemaLoader(self.template_dir.parent / "json_schema")
        self.image_prompts = ImagePromptLoader(self.template_dir, self.schemas)

        logger.info(f"Modular PromptLoader initialized from {self.template_dir}")

    def reload(self) -> None:
        """Reload all loaders (hot-reloading support)."""
        self.schemas.reload()
        logger.info("All prompt modules reloaded")

    def get_image_prompt_enhancement_prompt(self, user_base_prompt: str) -> Dict[str, str]:
        """Get prompt payload to enhance an AI image generation prompt."""
        return self.image_prompts.get_image_prompt_enhancement_prompt(user_base_prompt)


# Singleton pattern for easy access
_prompt_loader = None


def get_prompt_loader(template_dir: Optional[str] = None) -> PromptLoader:
    """
    Get or create a singleton instance of PromptLoader.

    Args:
        template_dir: Optional path to templates directory.

    Returns:
        PromptLoader: Singleton instance.
    """
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader(template_dir)
    return _prompt_loader
