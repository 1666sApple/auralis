"""
branding/logo_handler.py
========================
Task 2.2 — Logo integration with transparency and position control.

Handles:
  - Loading logo PNGs with alpha channel
  - Scaling logos to target size while preserving aspect ratio
  - Placing logos at brand-canonical positions
  - Ensuring logos never overlap text regions (bounding box check)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image


# ─────────────────────────────────────────────────────────────────────────────
# Logo placement presets
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LogoConfig:
    """
    Describes how to place a logo on an ad image.

    anchor_x  : "left" | "center" | "right"
    anchor_y  : "top"  | "center" | "bottom"
    margin_x  : Pixels from the horizontal edge
    margin_y  : Pixels from the vertical edge
    max_width_pct   : Max logo width as fraction of image width
    max_height_pct  : Max logo height as fraction of image height
    opacity   : 0.0-1.0 logo opacity
    """
    anchor_x: str = "left"
    anchor_y: str = "top"
    margin_x: int = 20
    margin_y: int = 20
    max_width_pct: float = 0.20
    max_height_pct: float = 0.12
    opacity: float = 1.0


# Brand-canonical logo positions
BRAND_LOGO_CONFIGS = {
    "airtel": LogoConfig(
        anchor_x="right", anchor_y="top",
        margin_x=48, margin_y=36,
        max_width_pct=0.28, max_height_pct=0.20,
        opacity=1.0,
    ),
    "robi": LogoConfig(
        anchor_x="left", anchor_y="top",
        margin_x=20, margin_y=16,
        max_width_pct=0.16, max_height_pct=0.09,
        opacity=1.0,
    ),
    "generic": LogoConfig(
        anchor_x="right", anchor_y="top",
        margin_x=20, margin_y=16,
        max_width_pct=0.18, max_height_pct=0.10,
        opacity=0.9,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Core functions
# ─────────────────────────────────────────────────────────────────────────────

def load_logo(logo_path: str | Path) -> Image.Image:
    """Load a logo PNG, ensuring RGBA mode."""
    img = Image.open(logo_path).convert("RGBA")
    return img


def scale_logo(
    logo: Image.Image,
    max_w: int,
    max_h: int,
) -> Image.Image:
    """Scale logo to fit within (max_w, max_h), preserving aspect ratio."""
    lw, lh = logo.size
    scale = min(max_w / lw, max_h / lh, 1.0)  # never upscale
    new_w = max(1, int(lw * scale))
    new_h = max(1, int(lh * scale))
    return logo.resize((new_w, new_h), Image.LANCZOS)


def compute_logo_position(
    config: LogoConfig,
    logo_w: int,
    logo_h: int,
    image_w: int,
    image_h: int,
) -> Tuple[int, int]:
    """Return (x, y) top-left position for the logo on the image."""
    mx, my = config.margin_x, config.margin_y

    if config.anchor_x == "left":
        x = mx
    elif config.anchor_x == "center":
        x = (image_w - logo_w) // 2
    else:  # right
        x = image_w - logo_w - mx

    if config.anchor_y == "top":
        y = my
    elif config.anchor_y == "center":
        y = (image_h - logo_h) // 2
    else:  # bottom
        y = image_h - logo_h - my

    return (max(x, 0), max(y, 0))


def _check_overlap(
    logo_box: Tuple[int, int, int, int],   # (x1, y1, x2, y2)
    text_boxes: list[Tuple[int, int, int, int]],
    threshold: float = 0.3,
) -> bool:
    """Return True if logo overlaps any text box by more than threshold."""
    lx1, ly1, lx2, ly2 = logo_box
    logo_area = max((lx2 - lx1) * (ly2 - ly1), 1)

    for (tx1, ty1, tx2, ty2) in text_boxes:
        ix1 = max(lx1, tx1)
        iy1 = max(ly1, ty1)
        ix2 = min(lx2, tx2)
        iy2 = min(ly2, ty2)
        if ix2 > ix1 and iy2 > iy1:
            inter = (ix2 - ix1) * (iy2 - iy1)
            if inter / logo_area > threshold:
                return True
    return False


class LogoHandler:
    """
    Composites a logo onto a PIL Image using brand config.

    Usage:
        handler = LogoHandler()
        result = handler.paste(
            base_image, logo_path="assets/airtel_logo.png", brand="airtel"
        )
    """

    def paste(
        self,
        base: Image.Image,
        logo_path: Optional[str | Path],
        brand: str = "airtel",
        config: Optional[LogoConfig] = None,
        text_boxes: Optional[list[Tuple[int, int, int, int]]] = None,
        fallback_anchor_x: str = "right",
    ) -> Image.Image:
        """
        Paste logo onto base image.

        Args:
            base          : Base PIL image
            logo_path     : Path to logo PNG (RGBA)
            brand         : "airtel" | "robi" | "generic"
            config        : Override LogoConfig (if None, uses brand preset)
            text_boxes    : List of (x1,y1,x2,y2) text regions to avoid
            fallback_anchor_x : If overlap detected, try this side instead

        Returns:
            New PIL Image (RGBA) with logo composited.
        """
        result = base.convert("RGBA")
        W, H = result.size

        if logo_path is None or not Path(logo_path).exists():
            return result  # No logo, return as-is

        cfg = config or BRAND_LOGO_CONFIGS.get(brand, BRAND_LOGO_CONFIGS["generic"])
        logo = load_logo(logo_path)

        max_w = int(W * cfg.max_width_pct)
        max_h = int(H * cfg.max_height_pct)
        logo = scale_logo(logo, max_w, max_h)
        lw, lh = logo.size

        lx, ly = compute_logo_position(cfg, lw, lh, W, H)

        # Check for overlap with text; try opposite side if needed
        if text_boxes and _check_overlap((lx, ly, lx + lw, ly + lh), text_boxes):
            fallback_cfg = LogoConfig(
                anchor_x=fallback_anchor_x,
                anchor_y=cfg.anchor_y,
                margin_x=cfg.margin_x,
                margin_y=cfg.margin_y,
                max_width_pct=cfg.max_width_pct,
                max_height_pct=cfg.max_height_pct,
                opacity=cfg.opacity,
            )
            lx, ly = compute_logo_position(fallback_cfg, lw, lh, W, H)

        # Apply opacity
        if cfg.opacity < 1.0:
            r, g, b, a = logo.split()
            a = a.point(lambda x: int(x * cfg.opacity))
            logo = Image.merge("RGBA", (r, g, b, a))

        # Composite
        result.paste(logo, (lx, ly), logo)
        return result

    def paste_watermark(
        self,
        base: Image.Image,
        logo_path: str | Path,
        opacity: float = 0.15,
        scale: float = 0.08,
    ) -> Image.Image:
        """
        Paste a subtle watermark logo at the bottom-right corner.
        """
        result = base.convert("RGBA")
        W, H = result.size

        logo = load_logo(logo_path)
        max_dim = int(min(W, H) * scale)
        logo = scale_logo(logo, max_dim, max_dim)
        lw, lh = logo.size

        r, g, b, a = logo.split()
        a = a.point(lambda x: int(x * opacity))
        logo = Image.merge("RGBA", (r, g, b, a))

        margin = int(min(W, H) * 0.02)
        result.paste(logo, (W - lw - margin, H - lh - margin), logo)
        return result
