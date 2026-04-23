"""
renderer/effects.py
===================
Readability effects, brand color palettes, and adaptive contrast.

Effects:
  - Background boxes, gradient bars, vignettes
  - Drop shadows on pre-rendered layers
  - Adaptive contrast: auto-picks text colors based on background luminance

Brand Palettes:
  - Airtel (official Gen Z / Gen Alpha palette)
  - Robi
"""

from __future__ import annotations

from typing import Tuple, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ─────────────────────────────────────────────────────────────────────────────
# Color type aliases
# ─────────────────────────────────────────────────────────────────────────────

RGBA = Tuple[int, int, int, int]       # 0-255
RGBAf = Tuple[float, float, float, float]  # 0.0-1.0


def rgba_i(r: float, g: float, b: float, a: float = 1.0) -> RGBA:
    """Convert 0-1 floats to 0-255 ints."""
    return (int(r * 255), int(g * 255), int(b * 255), int(a * 255))


def rgba_f(r: int, g: int, b: int, a: int = 255) -> RGBAf:
    """Convert 0-255 ints to 0-1 floats."""
    return (r / 255.0, g / 255.0, b / 255.0, a / 255.0)


# ─────────────────────────────────────────────────────────────────────────────
# Background box (rounded rectangle)
# ─────────────────────────────────────────────────────────────────────────────

def add_background_box(
    base: Image.Image,
    region: Tuple[int, int, int, int],  # (x, y, w, h)
    color: RGBA = (0, 0, 0, 160),
    radius: int = 16,
) -> Image.Image:
    """Draw a semi-transparent rounded background box."""
    result = base.convert("RGBA")
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x, y, w, h = region
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=color)
    return Image.alpha_composite(result, overlay)


def add_gradient_bar(
    base: Image.Image,
    region: Tuple[int, int, int, int],
    color_start: RGBA = (0, 0, 0, 200),
    color_end: RGBA = (0, 0, 0, 0),
    direction: str = "horizontal",
) -> Image.Image:
    """
    Draw a gradient bar using NumPy (smooth, fast).
    Replaces the old pixel-by-pixel approach.
    """
    x, y, w, h = region
    w = max(w, 1)
    h = max(h, 1)

    if direction == "horizontal":
        t = np.linspace(0, 1, w, dtype=np.float32)
        t = np.tile(t[np.newaxis, :], (h, 1))
    else:
        t = np.linspace(0, 1, h, dtype=np.float32)
        t = np.tile(t[:, np.newaxis], (1, w))

    arr = np.zeros((h, w, 4), dtype=np.uint8)
    for c in range(4):
        arr[:, :, c] = (
            color_start[c] * (1 - t) + color_end[c] * t
        ).astype(np.uint8)

    gradient = Image.fromarray(arr, "RGBA")
    result = base.convert("RGBA")
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    overlay.paste(gradient, (x, y))
    return Image.alpha_composite(result, overlay)


# ─────────────────────────────────────────────────────────────────────────────
# Vignette
# ─────────────────────────────────────────────────────────────────────────────

def add_vignette(
    base: Image.Image,
    strength: float = 0.5,
    color: Tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Add a radial vignette (darker edges) for text readability."""
    W, H = base.size
    result = base.convert("RGBA")

    # Create radial alpha mask using NumPy
    y_coords, x_coords = np.mgrid[0:H, 0:W]
    cx, cy = W / 2, H / 2
    dist = np.sqrt(((x_coords - cx) / (W / 2)) ** 2 +
                   ((y_coords - cy) / (H / 2)) ** 2)
    dist = np.clip(dist, 0, 1.5)

    # Vignette: dark at edges, transparent at center
    alpha = (dist ** 2 * strength * 255).clip(0, 255).astype(np.uint8)

    vignette_arr = np.zeros((H, W, 4), dtype=np.uint8)
    vignette_arr[:, :, 0] = color[0]
    vignette_arr[:, :, 1] = color[1]
    vignette_arr[:, :, 2] = color[2]
    vignette_arr[:, :, 3] = alpha

    vignette = Image.fromarray(vignette_arr, "RGBA")
    return Image.alpha_composite(result, vignette)


# ─────────────────────────────────────────────────────────────────────────────
# Drop shadow
# ─────────────────────────────────────────────────────────────────────────────

def drop_shadow_layer(
    text_layer: Image.Image,
    offset: Tuple[int, int] = (4, 4),
    blur_radius: int = 8,
    shadow_color: RGBA = (0, 0, 0, 180),
) -> Image.Image:
    """Create a drop shadow for a pre-rendered RGBA text layer."""
    W, H = text_layer.size
    result = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    alpha = text_layer.split()[3]
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow_solid = Image.new("RGBA", (W, H), shadow_color)
    shadow.paste(shadow_solid, mask=alpha)

    offset_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dx, dy = offset
    paste_x = max(dx, 0)
    paste_y = max(dy, 0)
    crop_x = max(-dx, 0)
    crop_y = max(-dy, 0)
    cropped = shadow.crop((crop_x, crop_y, W - max(dx, 0), H - max(dy, 0)))
    offset_img.paste(cropped, (paste_x, paste_y))
    blurred = offset_img.filter(ImageFilter.GaussianBlur(blur_radius))

    result = Image.alpha_composite(result, blurred)
    result = Image.alpha_composite(result, text_layer)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Brand color palettes — OFFICIAL Airtel & Robi
# ─────────────────────────────────────────────────────────────────────────────

class BrandPalette:
    """
    Canonical brand colors for Airtel / Robi Bangladesh.

    Airtel palette: Gen Z / Gen Alpha guidelines.
    """

    # ══════════════════════════════════════════════════════════════════════
    # AIRTEL — Official Palette
    # ══════════════════════════════════════════════════════════════════════

    # Primary
    AIRTEL_RED          = (237,  28,  36, 255)
    AIRTEL_WHITE        = (255, 255, 255, 255)

    # Greyscale / Neutrals
    AIRTEL_GREY         = ( 80,  81,  84, 255)
    AIRTEL_DEEP_BLACK   = (  0,   0,   0, 255)
    AIRTEL_LIGHT_GREY   = (151, 153, 156, 255)

    # Secondary (Accents)
    AIRTEL_GOLDEN_YELLOW = (253, 196,   0, 255)
    AIRTEL_ORANGE        = (242, 148,   0, 255)
    AIRTEL_PURPLE        = (146,  96, 160, 255)
    AIRTEL_TEAL          = (126, 191, 176, 255)
    AIRTEL_LIME          = (211, 208,   0, 255)

    # Derived
    AIRTEL_RED_DARK      = (180,  15,  20, 255)

    # ══════════════════════════════════════════════════════════════════════
    # ROBI
    # ══════════════════════════════════════════════════════════════════════

    ROBI_RED             = (226,  35,  26, 255)
    ROBI_RED_DARK        = (170,  20,  10, 255)
    ROBI_WHITE           = (255, 255, 255, 255)
    ROBI_ORANGE          = (255, 102,   0, 255)
    ROBI_DARK            = ( 30,  30,  30, 255)

    # ── Conversions ──────────────────────────────────────────────────────

    @staticmethod
    def to_float(rgba_255: RGBA) -> RGBAf:
        return tuple(c / 255.0 for c in rgba_255)  # type: ignore

    @staticmethod
    def to_int(rgba_f: RGBAf) -> RGBA:
        return tuple(int(c * 255) for c in rgba_f)  # type: ignore

    @staticmethod
    def brand_params(brand: str, font_size: int = 48) -> "RenderParams":
        """Return pre-configured RenderParams for a given brand."""
        from src.overlay.renderer.font_engine import RenderParams

        if brand.lower() == "airtel":
            return RenderParams(
                font_family="NotoSansBengali-Bold",
                font_size=font_size,
                bold=True,
                color=BrandPalette.to_float(BrandPalette.AIRTEL_WHITE),
                stroke_color=BrandPalette.to_float(BrandPalette.AIRTEL_RED_DARK),
                stroke_width=3.5,
                shadow_offset=(3, 3),
                shadow_blur=6,
                shadow_color=(0.0, 0.0, 0.0, 0.65),
            )
        elif brand.lower() == "robi":
            return RenderParams(
                font_family="NotoSansBengali-Bold",
                font_size=font_size,
                bold=True,
                color=BrandPalette.to_float(BrandPalette.ROBI_WHITE),
                stroke_color=BrandPalette.to_float(BrandPalette.ROBI_RED_DARK),
                stroke_width=3.0,
                shadow_offset=(2, 2),
                shadow_blur=5,
                shadow_color=(0.0, 0.0, 0.0, 0.6),
            )
        else:
            return RenderParams(font_size=font_size)


# ─────────────────────────────────────────────────────────────────────────────
# Adaptive contrast — auto-picks text color based on background
# ─────────────────────────────────────────────────────────────────────────────

def analyze_luminance(
    image: Image.Image,
    region: Tuple[int, int, int, int],  # (x, y, w, h)
) -> float:
    """
    Compute average luminance (0.0 = black, 1.0 = white) of an image region.
    Uses perceived luminance formula: 0.299R + 0.587G + 0.114B
    """
    x, y, w, h = region
    img_arr = np.array(image.convert("RGB"))
    H_img, W_img = img_arr.shape[:2]

    x1 = max(0, min(x, W_img))
    y1 = max(0, min(y, H_img))
    x2 = max(0, min(x + w, W_img))
    y2 = max(0, min(y + h, H_img))

    if x2 <= x1 or y2 <= y1:
        return 0.5

    crop = img_arr[y1:y2, x1:x2].astype(np.float32) / 255.0
    luminance = 0.299 * crop[:, :, 0] + 0.587 * crop[:, :, 1] + 0.114 * crop[:, :, 2]
    return float(luminance.mean())


def choose_contrast_params(
    luminance: float,
    brand: str = "airtel",
) -> dict:
    """
    Choose optimal text + stroke colors based on background luminance.

    Returns a dict of RenderParams overrides.
    Dark background → white text with brand-color stroke
    Light background → brand-color text with dark stroke
    """
    bp = BrandPalette

    if brand.lower() == "airtel":
        if luminance < 0.45:
            # Dark background: white text, red stroke
            return {
                "color": bp.to_float(bp.AIRTEL_WHITE),
                "stroke_color": bp.to_float(bp.AIRTEL_RED),
                "stroke_width": 3.5,
                "shadow_color": (0.0, 0.0, 0.0, 0.7),
            }
        else:
            # Light background: red text, dark stroke
            return {
                "color": bp.to_float(bp.AIRTEL_RED),
                "stroke_color": bp.to_float(bp.AIRTEL_WHITE),
                "stroke_width": 4.0,
                "shadow_color": (0.0, 0.0, 0.0, 0.5),
            }
    elif brand.lower() == "robi":
        if luminance < 0.45:
            return {
                "color": bp.to_float(bp.ROBI_WHITE),
                "stroke_color": bp.to_float(bp.ROBI_RED),
                "stroke_width": 3.0,
                "shadow_color": (0.0, 0.0, 0.0, 0.7),
            }
        else:
            return {
                "color": bp.to_float(bp.ROBI_RED),
                "stroke_color": bp.to_float(bp.ROBI_WHITE),
                "stroke_width": 3.5,
                "shadow_color": (0.0, 0.0, 0.0, 0.5),
            }
    else:
        if luminance < 0.45:
            return {
                "color": (1.0, 1.0, 1.0, 1.0),
                "stroke_color": (0.0, 0.0, 0.0, 1.0),
                "stroke_width": 3.0,
            }
        else:
            return {
                "color": (0.1, 0.1, 0.1, 1.0),
                "stroke_color": (1.0, 1.0, 1.0, 0.9),
                "stroke_width": 3.0,
            }


# ─────────────────────────────────────────────────────────────────────────────
# Price badge (legacy — kept for backward compat, prefer PillBadge)
# ─────────────────────────────────────────────────────────────────────────────

def draw_price_badge(
    base: Image.Image,
    price_text: str,
    position: Tuple[int, int],
    badge_color: RGBA = (237, 28, 36, 255),
    text_color: RGBA = (255, 255, 255, 255),
    font_path: str = "",
    font_size: int = 36,
    padding: int = 16,
    radius: int = 40,
) -> Image.Image:
    """Draw a pill-shaped price badge (e.g. '৳৪৯')."""
    result = base.convert("RGBA")
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default(size=font_size)
    except Exception:
        font = ImageFont.load_default(size=font_size)

    bb = draw.textbbox((0, 0), price_text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]

    x, y = position
    bw = tw + padding * 2
    bh = th + padding * 2

    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=radius, fill=badge_color)
    draw.text((x + padding, y + padding), price_text, font=font, fill=text_color)

    return Image.alpha_composite(result, overlay)
