import os
from pathlib import Path
from typing import Optional, List
from fastapi import HTTPException

from fastapi.responses import JSONResponse
from src.overlay.pipeline.orchestrator import AdOrchestrator
from src.overlay.templates.style_templates import OfferData
from src.api.models import OfferDetails, SimplifiedOverlayRequest
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)


class OverlayService:

    def __init__(self, output_dir: str = "output"):
        # AdOrchestrator handles its own font and logo management
        self.orchestrator = AdOrchestrator(output_dir=output_dir)

    def _normalize_path(self, path: str) -> str:
        """
        Robustly normalize paths, handling:
        1. Quotes (from Windows copy-paste)
        2. Slash inconsistencies
        3. Windows absolute paths in WSL (e.g., C:/ -> /mnt/c/)
        4. Common typos (e.g., asset instead of assets)
        """
        if not path:
            return path
            
        # 1. Strip quotes and fix slashes
        path = path.strip('"').strip("'").replace("\\", "/")
        
        # 2. Handle Windows Drive Letters in WSL (POSIX systems)
        if os.name == "posix":
            # Check for drive pattern like "C:/" or "D:/"
            if len(path) > 2 and path[1] == ":" and path[2] == "/":
                drive = path[0].lower()
                path = f"/mnt/{drive}{path[2:]}"

        # 3. Handle common typos (asset -> assets)
        if not Path(path).exists():
            # Try some common variations
            variations = [
                path.replace("/asset/", "/assets/"),
                path.replace("/assets/", "/asset/"),
                path.replace("/image/", "/images/"),
            ]
            for var in variations:
                if Path(var).exists():
                    logger.info(f"  ↪ Path corrected via variation: {var}")
                    return var
                    
        return path

    async def apply_overlay(
        self,
        image_path: str,
        offer_details: OfferDetails,
        template: str = "banner",
        logo_path: Optional[str] = None
    ) -> str:

        """Applies a branded text overlay to an existing image."""
        
        # 0. Sanitize paths
        image_path = self._normalize_path(image_path)
        if logo_path:
            logo_path = self._normalize_path(logo_path)
            
        logger.info(f"Target Image: {image_path}")

        offer = OfferData(
            headline_bn=offer_details.headline_bn or "",
            headline_en=offer_details.headline_en or "",
            subline_bn=offer_details.subline_bn or "",
            subline_en=offer_details.subline_en or "",
            price=offer_details.price or "",
            data_gb=offer_details.data_gb or "",
            validity=offer_details.validity or "",
            brand=offer_details.brand,
            lang=offer_details.lang
        )

        # 2. Render the ad
        output_path = await self.orchestrator.render_single(
            image_path=image_path,
            offer=offer,
            template=template,
            logo_path=logo_path
        )

        
        return str(output_path)

    async def full_pipeline_flow(
        self,
        image_path: str,
        offer_details: OfferDetails,
        template: str = "banner"
    ) -> str:

        """A simple wrapper for consistency with ImageGeneratorService."""
        return await self.apply_overlay(image_path, offer_details, template)


    async def apply_simplified_overlay(
        self,
        request: SimplifiedOverlayRequest
    ) -> List[str]:

        """Simplified batch overlay API mapping tagline/offer to internal structures."""
        
        # 1. Resolve image paths (singular or list)
        images = request.images or []
        if request.image_path:
            images.append(request.image_path)
            
        if not images:
            # We use 422 for consistency with other validation errors
            return JSONResponse(status_code=422, content={"status": "error", "message": "No source images provided"})

        # 2. Map simplified inputs to OfferData
        offer = OfferData(
            headline_bn=request.headline_bn,
            subline_bn=request.subline_bn or "",
            price=request.price or "",
            data_gb=request.data_gb or "",
            validity=request.validity or "",
            brand=request.brand.lower(),
            lang="bn" # Defaulting to Bengali for local CVM outreach
        )

        # 3. Batch render (returns List[Path])
        # Note: render_batch will need to be async or handle concurrent renders
        output_paths = await self.orchestrator.render_batch(
            image_paths=[self._normalize_path(img) for img in images],
            offers=[offer],
            templates=[request.template]
        )


        return [str(p) for p in output_paths]



