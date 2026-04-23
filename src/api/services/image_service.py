import os
import json
import base64
from pathlib import Path
from typing import Tuple, Optional
from io import BytesIO
from PIL import Image
from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger
from src.shared.utils.auth_helper import get_boto3_client
from src.generator.intelligence.langchain_llm import get_langchain_llm
from src.generator.prompts.loaders.image_prompt_loader import ImagePromptLoader
from src.generator.prompts.loaders.schema_loader import SchemaLoader

logger = get_logger(__name__)


class ImageGeneratorService:
    def __init__(self):
        self.llm = get_langchain_llm()

        # Setup Prompt Loader
        template_dir = Path("src/generator/prompts/templates")
        schema_dir = Path("src/generator/prompts/json_schema")
        self.schemas = SchemaLoader(schema_dir)
        self.prompt_loader = ImagePromptLoader(template_dir, self.schemas)

        # Bedrock Runtime for Image Generation (AP-NORTHEAST-1 for SDXL)
        self.bedrock_runtime = get_boto3_client("bedrock-runtime", settings.AWS_REGION_IMAGE)

    def enhance_prompt(
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
    ) -> str:
        """Uses LLM to enhance the user's raw prompt into a detailed artistic prompt.
        Returns the full Markdown response from the LLM.
        """
        prompts = self.prompt_loader.get_image_prompt_enhancement_prompt(
            user_prompt=user_prompt,
            brand=brand,
            aspect_ratio=aspect_ratio,
            gender=gender,
            background_type=background_type,
            texture_type=texture_type,
            activity=activity,
            hair_length=hair_length,
            hair_texture=hair_texture,
        )

        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            response, _ = self.llm.invoke_llm(
                system_prompt=prompts["system"],
                user_prompt=prompts["human"],
                track_as="image_prompt_enhancement",
            )

            if response and response.strip():
                logger.info(
                    f"\n--- RAW LLM RESPONSE (Attempt {attempt + 1}) ---\n{response}\n------------------------"
                )
                return response
            else:
                logger.warning(
                    f"Attempt {attempt + 1}: LLM returned an empty response. Retrying..."
                )

        logger.error(
            f"LLM consistently failed to generate a valid prompt after {MAX_RETRIES} attempts."
        )
        raise ValueError(
            "LLM failed to generate an enhanced prompt. The model might be blocking the request or rejecting the template."
        )

    def _extract_prompt_string(self, markdown_response: str) -> str:
        """Internal helper to extract the actual prompt string for the image generator."""
        import re

        match = re.search(
            r"<prompt>\s*(.*?)\s*</prompt>",
            markdown_response,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

        return (
            markdown_response.replace("<prompt>", "").replace("</prompt>", "").strip()
        )

    def generate_image(self, enhanced_prompt: str, aspect_ratio: str = "1:1") -> str:
        """Calls AWS Bedrock (SDXL) to generate the actual image."""
        output_dir = Path("data/generated")
        output_dir.mkdir(parents=True, exist_ok=True)

        width, height = 1024, 1024
        if aspect_ratio == "1:1":
            width, height = 1344, 768
        elif aspect_ratio == "9:16":
            width, height = 768, 1344

        payload = {
            "text_prompts": [{"text": enhanced_prompt, "weight": 1.0}],
            "cfg_scale": 7.5,
            "steps": 30,
            "seed": 42,
            "width": width,
            "height": height,
        }

        model_id = (
            settings.IMAGE_MODEL_ID
            if "stability" in settings.IMAGE_MODEL_ID.lower()
            else "stability.stable-diffusion-xl-v1:0"
        )
        logger.info(
            f"Invoking Bedrock Image Gen ({model_id}) with prompt: {enhanced_prompt[:100]}..."
        )

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload),
            )

            response_body = json.loads(response.get("body").read())
            image_data = base64.b64decode(
                response_body.get("artifacts")[0].get("base64")
            )

            filename = f"gen_{os.urandom(4).hex()}.png"
            file_path = output_dir / filename

            with open(file_path, "wb") as f:
                f.write(image_data)

            return str(file_path)
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise

    def full_generation_flow(
        self,
        user_prompt: str,
        brand: str = "robi",
        aspect_ratio: str = "1:1",
        gender: Optional[str] = None,
        background_type: Optional[str] = None,
        texture_type: Optional[str] = None,
        activity: Optional[str] = None,
        hair_length: Optional[str] = None,
        hair_texture: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Runs the enhancement and generation end-to-end for internal pipeline use."""
        full_markdown = self.enhance_prompt(
            user_prompt=user_prompt,
            brand=brand,
            aspect_ratio=aspect_ratio,
            gender=gender,
            background_type=background_type,
            texture_type=texture_type,
            activity=activity,
            hair_length=hair_length,
            hair_texture=hair_texture,
        )
        prompt_string = self._extract_prompt_string(full_markdown)
        image_path = self.generate_image(prompt_string, aspect_ratio)
        return image_path, full_markdown

    def apply_logo_overlay(
        self,
        image_bytes: bytes,
        logo_bytes: bytes,
        position: str = "top-right",
        padding: int = 20,
        logo_scale: float = 0.15,
        rotation: float = 0.0,
        opacity: float = 1.0,
        x_offset: int = 0,
        y_offset: int = 0,
        original_filename: str = None,
    ) -> str:
        """
        Place a logo PNG on an image with dynamic positioning and rotation.

        Args:
            image_bytes: Raw bytes of main image
            logo_bytes: Raw bytes of logo PNG (can be empty if no logo to add)
            position: Logo position (top-left, top-center, top-right,
                      center-left, center, center-right,
                      bottom-left, bottom-center, bottom-right)
            padding: Pixels from the edge
            logo_scale: Logo size relative to image width (0.0-1.0)
            rotation: Rotation angle in degrees (-360 to 360)
            opacity: Logo opacity (0.0 to 1.0)
            x_offset: Additional horizontal offset in pixels
            y_offset: Additional vertical offset in pixels

        Returns:
            Path to the saved output image
        """
        try:
            main_image = Image.open(BytesIO(image_bytes)).convert("RGBA")

            if not logo_bytes or len(logo_bytes) == 0:
                output_dir = Path("data/output")
                output_dir.mkdir(parents=True, exist_ok=True)
                if original_filename:
                    stem = Path(original_filename).stem
                    filename = f"{stem}.png"
                else:
                    filename = f"composed_{os.urandom(4).hex()}.png"
                output_path = output_dir / filename
                main_image.save(output_path, format="PNG")
                logger.info(f"No logo provided. Saved composed image to: {output_path}")
                return str(output_path)

            logo_image = Image.open(BytesIO(logo_bytes)).convert("RGBA")

            new_logo_width = int(main_image.width * logo_scale)
            aspect_ratio = logo_image.height / logo_image.width
            new_logo_height = int(new_logo_width * aspect_ratio)

            if new_logo_width > 0 and new_logo_height > 0:
                logo_image = logo_image.resize((new_logo_width, new_logo_height))

            if rotation != 0:
                logo_image = logo_image.rotate(
                    rotation, expand=True, resample=Image.Resampling.BICUBIC
                )

            if opacity < 1.0:
                alpha = logo_image.split()[3]
                alpha = alpha.point(lambda p: int(p * opacity))
                logo_image.putalpha(alpha)

            position_coords = {
                "top-left": (padding, padding),
                "top-center": ((main_image.width - logo_image.width) // 2, padding),
                "top-right": (main_image.width - logo_image.width - padding, padding),
                "center-left": (padding, (main_image.height - logo_image.height) // 2),
                "center": (
                    (main_image.width - logo_image.width) // 2,
                    (main_image.height - logo_image.height) // 2,
                ),
                "center-right": (
                    main_image.width - logo_image.width - padding,
                    (main_image.height - logo_image.height) // 2,
                ),
                "bottom-left": (
                    padding,
                    main_image.height - logo_image.height - padding,
                ),
                "bottom-center": (
                    (main_image.width - logo_image.width) // 2,
                    main_image.height - logo_image.height - padding,
                ),
                "bottom-right": (
                    main_image.width - logo_image.width - padding,
                    main_image.height - logo_image.height - padding,
                ),
            }

            pos = position_coords.get(position.lower(), position_coords["top-right"])
            final_pos = (pos[0] + x_offset, pos[1] + y_offset)

            result = main_image.copy()
            result.paste(logo_image, final_pos, logo_image)

            output_dir = Path("data/output")
            output_dir.mkdir(parents=True, exist_ok=True)

            if original_filename:
                stem = Path(original_filename).stem
                filename = f"{stem}.png"
            else:
                filename = f"logo_overlay_{os.urandom(4).hex()}.png"
            output_path = output_dir / filename
            result.save(output_path, format="PNG")

            logger.info(f"Logo overlay applied successfully. Saved to: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Logo overlay failed: {e}")
            raise