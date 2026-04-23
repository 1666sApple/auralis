from typing import Optional, List
from pydantic import BaseModel, Field


class BannerGenerationRequest(BaseModel):
    user_prompt: str = Field(
        ...,
        description="Short user idea for the image (e.g., 'A modern city skyline at night')",
    )
    brand: str = Field("airtel", description="Brand context (airtel or robi)")
    aspect_ratio: str = Field("1:1", description="Image aspect ratio")
    gender: Optional[str] = Field(None, description="Subject gender (male, female)")
    background_type: Optional[str] = Field(None, description="Background style (solid, doodly, textured)")
    texture_type: Optional[str] = Field(None, description="Predefined texture (recycled_paper, linen_weave, fine_grain_plaster)")
    activity: Optional[str] = Field(None, description="Specific activity (gaming, music, calling, etc.)")
    hair_length: Optional[str] = Field(None, description="Male hair length (medium, long)")
    hair_texture: Optional[str] = Field(None, description="Male hair texture (straight, curly, wavy_mixed)")


class OfferDetails(BaseModel):
    headline_bn: Optional[str] = None
    headline_en: Optional[str] = None
    subline_bn: Optional[str] = None
    subline_en: Optional[str] = None
    price: Optional[str] = None
    data_gb: Optional[str] = None
    validity: Optional[str] = None
    cta_bn: Optional[str] = Field("এখনই কিনুন", description="Call to action in Bengali")
    cta_en: Optional[str] = Field("Buy Now", description="Call to action in English")
    brand: str = "airtel"
    lang: str = "bn"


class OverlayRequest(BaseModel):
    image_path: str = Field(..., description="Path to the source image")
    offer: OfferDetails
    template: str = Field("banner", description="Template name (banner, story, etc.)")
    logo_path: Optional[str] = None


class SimplifiedOverlayRequest(BaseModel):
    # Support both singular and plural for convenience
    image_path: Optional[str] = Field(None, description="Path to a single source image")
    images: Optional[List[str]] = Field(None, description="List of source image paths")

    # Naming aligned with internal 'OfferData' and 'build_offer'
    headline_bn: str = Field(..., description="Primary tagline (Bengali/English)")
    subline_bn: Optional[str] = Field(None, description="Secondary promotional text")

    price: Optional[str] = None
    data_gb: Optional[str] = None
    validity: Optional[str] = None

    brand: str = Field("airtel", description="Brand name (airtel or robi)")
    template: str = Field("banner", description="Template name (banner, story, etc.)")


class FullPipelineRequest(BaseModel):
    user_prompt: str
    offer: OfferDetails
    template: str = "banner"
    aspect_ratio: str = "1:1"
    gender: Optional[str] = None
    background_type: Optional[str] = None
    texture_type: Optional[str] = None
    activity: Optional[str] = None
    hair_length: Optional[str] = None
    hair_texture: Optional[str] = None


class ApiResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None
