import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError

from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger
from src.api.models import (
    BannerGenerationRequest,
    OverlayRequest,
    FullPipelineRequest,
    ApiResponse,
    SimplifiedOverlayRequest,
)
from fastapi import UploadFile, File, Form

from src.api.services.image_service import ImageGeneratorService
from src.api.services.overlay_service import OverlayService

logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Unified API for Generative Image Generation and Branded Text Overlay",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Services
image_service = ImageGeneratorService()
overlay_service = OverlayService()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.post("/v1/generator/generate", response_model=ApiResponse)
async def generate_prompt(request: BannerGenerationRequest):
    """Enhance a raw user prompt into a structured artistic prompt template."""
    try:
        enhanced_markdown = image_service.enhance_prompt(
            user_prompt=request.user_prompt,
            brand=request.brand,
            aspect_ratio=request.aspect_ratio,
            gender=request.gender,
            background_type=request.background_type,
            texture_type=request.texture_type,
            activity=request.activity,
            hair_length=request.hair_length,
            hair_texture=request.hair_texture,
        )
        return ApiResponse(
            status="success",
            message="Prompt enhanced successfully",
            data={"enhanced_prompt": enhanced_markdown},
        )
    except Exception as e:
        logger.error(f"Prompt enhancement error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/overlay/apply", response_model=ApiResponse)
async def apply_overlay(request: OverlayRequest):
    """Apply a branded text overlay to an existing image."""
    try:
        output_path = await overlay_service.apply_overlay(
            image_path=request.image_path,
            offer_details=request.offer,
            template=request.template,
            logo_path=request.logo_path,
        )

        return ApiResponse(
            status="success",
            message="Overlay applied successfully",
            data={"ad_path": output_path},
        )
    except Exception as e:
        logger.error(f"Overlay error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/overlay/simplified", response_model=ApiResponse)
async def apply_simplified_overlay(request: SimplifiedOverlayRequest):
    """Simplified batch overlay API mapping tagline/offer to images."""
    try:
        output_paths = await overlay_service.apply_simplified_overlay(request)

        return ApiResponse(
            status="success",
            message=f"Overlay applied to {len(output_paths)} images successfully",
            data={"ad_paths": output_paths},
        )
    except Exception as e:
        logger.error(f"Simplified overlay error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/overlay/logo", response_model=ApiResponse)
async def apply_logo_overlay(
    image: UploadFile = File(..., description="Main image file"),
    logo: UploadFile = File(..., description="Logo PNG file"),
    position: str = Form(
        "top-right",
        description="Logo position: top-left, top-center, top-right, center-left, center, center-right, bottom-left, bottom-center, bottom-right",
    ),
    padding: int = Form(20, description="Padding from edge in pixels"),
    logo_scale: float = Form(
        0.15, description="Logo scale relative to image width (0.0-1.0)"
    ),
    rotation: float = Form(0.0, description="Rotation angle in degrees (-360 to 360)"),
    opacity: float = Form(1.0, description="Logo opacity (0.0 to 1.0)"),
    x_offset: int = Form(0, description="Additional horizontal offset in pixels"),
    y_offset: int = Form(0, description="Additional vertical offset in pixels"),
):
    """Place a logo PNG on an image with dynamic positioning and rotation."""
    try:
        result_path = image_service.apply_logo_overlay(
            image_bytes=await image.read(),
            logo_bytes=await logo.read(),
            position=position,
            padding=padding,
            logo_scale=logo_scale,
            rotation=rotation,
            opacity=opacity,
            x_offset=x_offset,
            y_offset=y_offset,
            original_filename=image.filename,
        )

        return ApiResponse(
            status="success",
            message="Logo overlay applied successfully",
            data={"output_path": result_path},
        )
    except Exception as e:
        logger.error(f"Logo overlay error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{file_path:path}")
async def serve_file(file_path: str):
    """Serve composited output images for frontend download."""
    # Only allow serving from the data/output directory
    safe_path = os.path.normpath(file_path)
    if not safe_path.startswith("data/output") and not safe_path.startswith("data\\output"):
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(safe_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(safe_path, media_type="image/png")


@app.post("/v1/pipeline/full", response_model=ApiResponse)
async def full_pipeline(request: FullPipelineRequest):
    """Full Pipeline: Generate Image -> Apply Branded Overlay."""
    try:
        # Step 1: Generate image
        image_path, enhanced_prompt = image_service.full_generation_flow(
            user_prompt=request.user_prompt,
            brand=request.offer.brand,
            aspect_ratio=request.aspect_ratio,
            gender=request.gender,
            background_type=request.background_type,
            texture_type=request.texture_type,
            activity=request.activity,
            hair_length=request.hair_length,
            hair_texture=request.hair_texture,
        )

        # Step 2: Apply overlay
        final_ad_path = await overlay_service.apply_overlay(
            image_path=image_path,
            offer_details=request.offer,
            template=request.template,
        )

        return ApiResponse(
            status="success",
            message="Full ad generation complete",
            data={
                "image_path": image_path,
                "final_ad_path": final_ad_path,
                "enhanced_prompt": enhanced_prompt,
            },
        )
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Catch Pydantic/FastAPI validation errors and provide helpful feedback
    specifically for common Windows path JSON escape issues.
    """
    errors = exc.errors()
    helpful_msg = "Validation error occurred"

    # Check for the specific "Invalid \escape" error we saw in the user log
    for error in errors:
        msg = error.get("msg", "")
        ctx_err = error.get("ctx", {}).get("error", "")

        if error.get("type") == "json_invalid" and (
            "Invalid \\escape" in ctx_err or "Invalid \\escape" in msg
        ):
            helpful_msg = (
                "JSON Decode Error: Invalid escape sequence detected in your Windows path. "
                "JSON strings cannot contain single backslashes (\\) like 'C:\\Users'. "
                "Please double every backslash in your paths (\\\\). "
                "Example: 'C:\\\\Users\\\\mdasifurrahman.a\\\\...'"
            )
            break
        elif error.get("type") == "value_error.missing":
            field = " -> ".join(str(loc) for loc in error.get("loc", []))
            helpful_msg = f"Missing required field: {field}"

    logger.warning(f"Validation error: {helpful_msg} | Original: {errors}")
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": helpful_msg, "detail": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error handler caught: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "An internal server error occurred",
            "detail": str(exc),
        },
    )
