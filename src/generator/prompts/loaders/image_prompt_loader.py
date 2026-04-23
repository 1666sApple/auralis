import json
from pathlib import Path
from typing import Dict, Any, Optional
from src.shared.logger.logger_config import get_logger
from src.generator.prompts.loaders.schema_loader import SchemaLoader

logger = get_logger(__name__)

class ImagePromptLoader:
    """
    Dedicated loader for Image Generation Prompt Enhancer templates.
    Handles the Master System Prompt, Style References, and JSON Schema injection.
    """

    def __init__(self, template_dir: Path, schemas: SchemaLoader):
        """
        Initialize the ImagePromptLoader.

        Args:
            template_dir: Path to the directory containing XML templates.
            schemas: SchemaLoader instance for loading JSON schemas.
        """
        self.template_dir = template_dir
        self.schemas = schemas
        logger.info(f"ImagePromptLoader initialized with templates from {template_dir}")

    def _read_template(self, filename: str) -> str:
        """Utility to read template content."""
        file_path = self.template_dir / filename
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Template not found: {file_path}")
            return f"Error: {filename} not found."
        except Exception as e:
            logger.error(f"Error reading {file_path}: {str(e)}")
            return ""

    def get_image_prompt_enhancement_prompt(
        self,
        user_prompt: str,
        brand: str = "airtel",
        aspect_ratio: str = "1:1",
        gender: Optional[str] = None,
        background_type: Optional[str] = None,
        texture_type: Optional[str] = None,
        activity: Optional[str] = None,
        hair_length: Optional[str] = None,
        hair_texture: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Assemble the multi-stage system prompt. If specific parameters are provided,
        it builds a modular prompt by combining relevant components. 
        Otherwise, it falls back to the full brand-specific Markdown template.
        """
        brand_folder = brand.lower() if brand.lower() in ["airtel", "robi"] else "robi"
        
        # Check if we should use the modular system
        params = [gender, background_type, activity]
        use_modular = any(p is not None for p in params)

        if use_modular:
            logger.info(f"Assembling modular prompt for {brand_folder}")
            sys_prompt = self._assemble_modular_prompt(
                brand_folder=brand_folder,
                gender=gender,
                background_type=background_type,
                texture_type=texture_type,
                activity=activity,
                hair_length=hair_length,
                hair_texture=hair_texture
            )
        else:
            # Fallback to full master template
            logger.info(f"Falling back to master template for {brand_folder}")
            sys_prompt = self._read_template(f"{brand_folder}/enhancer.md")

        # Load common styles
        style_refs = self._read_template("common/styles.md")

        # Integrate everything into the System string
        integrated_system_prompt = f"""{sys_prompt}

## Style References
{style_refs}

## Critical Output Format
You MUST return ONLY a structured Markdown document.

# Enhanced Image Prompt
[The final master-level prompt string]

## Reasoning Summary
[Brief explanation of brand-specific choices]
"""

        # Build Final Payload
        human_prompt = (
            f"Please process the following image prompt request:\n\n"
            f"- **Target Brand:** {brand.upper()}\n"
            f"- **Requested Aspect Ratio:** {aspect_ratio}\n"
            f"- **User Core Prompt:** {user_prompt}\n"
        )
        
        if use_modular:
            human_prompt += f"- **Parameters:** {json.dumps({'gender': gender, 'background': background_type, 'activity': activity}, indent=2)}\n"

        human_prompt += f"\nEnsure the enhancement strictly adheres to the {brand.upper()} demographic rules."

        return {"system": integrated_system_prompt, "human": human_prompt}

    def _assemble_modular_prompt(
        self,
        brand_folder: str,
        gender: Optional[str] = None,
        background_type: Optional[str] = None,
        texture_type: Optional[str] = None,
        activity: Optional[str] = None,
        hair_length: Optional[str] = None,
        hair_texture: Optional[str] = None,
    ) -> str:
        """Assembles the system prompt from fragmented components."""
        components = []
        
        # 1. Base Components
        components.append(self._read_template(f"{brand_folder}/components/role.md"))
        components.append(self._read_template(f"{brand_folder}/components/core_principles.md"))
        
        # 2. Background (If specified)
        if background_type:
            bg_file = f"background_{background_type.lower()}.md"
            bg_content = self._read_template(f"{brand_folder}/components/{bg_file}")
            # If textured, we might want to inject the specific texture_type in the future,
            # but for now the component contains all predefined types.
            components.append(bg_content)
            
        # 3. Subject (If specified)
        if gender:
            # Mapping gender to filenames used during extraction
            gender_map = {
                "male": "subject_boy.md" if brand_folder == "airtel" else "subject_male.md",
                "female": "subject_girl.md" if brand_folder == "airtel" else "subject_female.md"
            }
            sub_file = gender_map.get(gender.lower())
            if sub_file:
                sub_content = self._read_template(f"{brand_folder}/components/{sub_file}")
                # Inject hair details if male
                if gender.lower() == "male" and (hair_length or hair_texture):
                    sub_content += f"\n**SPECIFIC HAIR INSTRUCTIONS**: Use {hair_length or 'medium'} length and {hair_texture or 'straight'} texture."
                components.append(sub_content)
        
        # 4. Activity (If specified)
        if activity:
            # Match the activity filenames
            act_file = f"activity_{activity.lower().replace(' ', '_')}.md"
            components.append(self._read_template(f"{brand_folder}/components/{act_file}"))
            
        # 5. Requirement Components
        components.append(self._read_template(f"{brand_folder}/components/strategic_formula.md"))
        components.append(self._read_template(f"{brand_folder}/components/constraints.md"))
        components.append(self._read_template(f"{brand_folder}/components/output_requirement.md"))
        
        # 6. Negative Anchoring (Airtel has a specific file, Robi might be common or in constraints)
        neg_file = f"{brand_folder}/components/negative_anchoring.md"
        if (self.template_dir / neg_file).exists():
             components.append(self._read_template(neg_file))
        
        return "\n\n".join(components)

