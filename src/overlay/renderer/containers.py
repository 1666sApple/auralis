"""
renderer/containers.py
======================
Fancy artistic text containers for professional telco ad banners.

Container types:
  GradientBadge  — Rounded rect with gradient fill + inner border
  FrostedPanel   — Semi-transparent blurred glass backdrop
  RibbonBanner   — Angled/folded ribbon shape with shadow
  BorderFrame    — Thin decorative border with subtle glow
  PillBadge      — Capsule/pill shape for prices & data tags
  AccentStrip    — Thin accent color bar above/below text
"""

from __future__ import annotations

from typing import Tuple, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

RGBA = Tuple[int, int, int, int]


# ─────────────────────────────────────────────────────────────────────────────
# Helper: smooth gradient generation
# ─────────────────────────────────────────────────────────────────────────────

def _lerp_color(c1: RGBA, c2: RGBA, t: float) -> RGBA:
    """Linearly interpolate between two RGBA colors."""
    return tuple(int(a * (1 - t) + b * t) for a, b in zip(c1, c2))


def _norm_color(color: RGBA) -> Tuple[int, int, int, int]:
    """Convert 0.0-1.0 float RGBA to 0-255 integer RGBA."""
    if any(c > 1.0 for c in color):
        return tuple(int(c) for c in color)  # Already 0-255
    return tuple(int(c * 255) for c in color)


def _make_gradient(
    width: int,
    height: int,
    color_start: RGBA,
    color_end: RGBA,
    direction: str = "horizontal",
) -> Image.Image:
    """Create a smooth gradient RGBA image using NumPy (fast)."""
    width, height = int(width), int(height)
    color_start = _norm_color(color_start)
    color_end = _norm_color(color_end)

    if direction == "horizontal":
        t = np.linspace(0, 1, width, dtype=np.float32)
        t = np.tile(t[np.newaxis, :], (height, 1))
    else:  # vertical
        t = np.linspace(0, 1, height, dtype=np.float32)
        t = np.tile(t[:, np.newaxis], (1, width))

    arr = np.zeros((height, width, 4), dtype=np.uint8)
    for c in range(4):
        # We handle float colors by multiplying by 255 if needed,
        # but _norm_color already did that for the input colors.
        arr[:, :, c] = (
            color_start[c] * (1 - t) + color_end[c] * t
        ).astype(np.uint8)

    return Image.fromarray(arr, "RGBA")



# ─────────────────────────────────────────────────────────────────────────────
# GradientBadge
# ─────────────────────────────────────────────────────────────────────────────

def gradient_badge(
    base: Image.Image,
    region: Tuple[int, int, int, int],  # (x, y, w, h)
    color_start: RGBA = (237, 28, 36, 240),
    color_end: RGBA = (180, 10, 20, 240),
    direction: str = "horizontal",
    radius: int = 16,
    border_color: RGBA = (255, 255, 255, 180),
    border_width: int = 2,
    shadow_offset: Tuple[int, int] = (3, 4),
    shadow_blur: int = 8,
    shadow_color: RGBA = (0, 0, 0, 120),
) -> Image.Image:
    """
    Draw a gradient-filled rounded badge with optional inner border and shadow.

    Ideal for: headlines, price callouts, section headers.
    """
    x, y, w, h = region
    # Robust normalization
    color_start = _norm_color(color_start)
    color_end = _norm_color(color_end)
    border_color = _norm_color(border_color)
    shadow_color = _norm_color(shadow_color)
    radius = int(radius)
    border_width = int(border_width)
    shadow_blur = int(shadow_blur)
    shadow_offset = (int(shadow_offset[0]), int(shadow_offset[1]))

    result = base.convert("RGBA")

    # ── Shadow ────────────────────────────────────────────────────────────
    if shadow_color[3] > 0:
        shadow_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        sx, sy = x + shadow_offset[0], y + shadow_offset[1]
        sd.rounded_rectangle(
            [sx, sy, sx + w, sy + h],
            radius=radius,
            fill=shadow_color,
        )
        if shadow_blur > 0:
            shadow_layer = shadow_layer.filter(
                ImageFilter.GaussianBlur(radius=shadow_blur)
            )
        result = Image.alpha_composite(result, shadow_layer)

    # ── Gradient fill ─────────────────────────────────────────────────────
    gradient = _make_gradient(w, h, color_start, color_end, direction)

    # Mask to rounded rect shape
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, w, h], radius=radius, fill=255)

    badge_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
    badge_layer.paste(gradient, (x, y), mask)
    result = Image.alpha_composite(result, badge_layer)

    # ── Border ────────────────────────────────────────────────────────────
    if border_width > 0 and border_color[3] > 0:
        border_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(border_layer)
        bd.rounded_rectangle(
            [x, y, x + w, y + h],
            radius=radius,
            outline=border_color,
            width=border_width,
        )
        result = Image.alpha_composite(result, border_layer)

    return result



# ─────────────────────────────────────────────────────────────────────────────
# FrostedPanel
# ─────────────────────────────────────────────────────────────────────────────

def frosted_panel(
    base: Image.Image,
    region: Tuple[int, int, int, int],  # (x, y, w, h)
    tint_color: RGBA = (0, 0, 0, 140),
    blur_radius: int = 12,
    radius: int = 20,
    border_color: RGBA = (255, 255, 255, 60),
    border_width: int = 1,
) -> Image.Image:
    """
    Semi-transparent blurred glass panel behind text.
    Creates a frosted-glass / glassmorphism effect.

    Ideal for: sublines, body paragraphs, info panels.
    """
    x, y, w, h = region
    # Robust normalization
    tint_color = _norm_color(tint_color)
    border_color = _norm_color(border_color)
    radius = int(radius)
    blur_radius = int(blur_radius)
    border_width = int(border_width)

    result = base.convert("RGBA")

    # Crop the region and blur it
    crop_x1 = int(max(0, x))
    crop_y1 = int(max(0, y))
    crop_x2 = int(min(result.width, x + w))
    crop_y2 = int(min(result.height, y + h))

    if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
        return result

    blurred_region = result.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    blurred_region = blurred_region.filter(
        ImageFilter.GaussianBlur(radius=blur_radius)
    )

    # Create a tinted overlay
    tint = Image.new("RGBA", blurred_region.size, tint_color)
    blurred_region = Image.alpha_composite(blurred_region, tint)

    # Mask to rounded rect
    actual_w = crop_x2 - crop_x1
    actual_h = crop_y2 - crop_y1
    mask = Image.new("L", (actual_w, actual_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        [0, 0, actual_w, actual_h], radius=radius, fill=255
    )

    panel_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
    panel_layer.paste(blurred_region, (crop_x1, crop_y1), mask)
    result = Image.alpha_composite(result, panel_layer)

    # Border
    if border_width > 0 and border_color[3] > 0:
        border_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(border_layer)
        bd.rounded_rectangle(
            [crop_x1, crop_y1, crop_x2, crop_y2],
            radius=radius,
            outline=border_color,
            width=border_width,
        )
        result = Image.alpha_composite(result, border_layer)

    return result



# ─────────────────────────────────────────────────────────────────────────────
# RibbonBanner
# ─────────────────────────────────────────────────────────────────────────────

def ribbon_banner(
    base: Image.Image,
    region: Tuple[int, int, int, int],  # (x, y, w, h)
    fill_color: RGBA = (237, 28, 36, 255),
    fold_color: RGBA = (160, 15, 20, 255),
    fold_size: int = 12,
    shadow_blur: int = 6,
    shadow_color: RGBA = (0, 0, 0, 100),
) -> Image.Image:
    """
    An angled/folded ribbon shape with a fold shadow underneath.

    Ideal for: "Limited offer!", CTA triggers, tag labels.
    """
    x, y, w, h = region
    # Robust normalization
    fill_color = _norm_color(fill_color)
    fold_color = _norm_color(fold_color)
    shadow_color = _norm_color(shadow_color)
    fold_size = int(fold_size)
    shadow_blur = int(shadow_blur)

    result = base.convert("RGBA")

    # ── Shadow ────────────────────────────────────────────────────────────
    if shadow_color[3] > 0:
        shadow_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        sd.rectangle([x + 2, y + 2, x + w + 2, y + h + 2], fill=shadow_color)
        if shadow_blur > 0:
            shadow_layer = shadow_layer.filter(
                ImageFilter.GaussianBlur(radius=shadow_blur)
            )
        result = Image.alpha_composite(result, shadow_layer)

    # ── Main ribbon body ──────────────────────────────────────────────────
    ribbon_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(ribbon_layer)
    rd.rectangle([x, y, x + w, y + h], fill=fill_color)

    # ── Fold triangle (bottom-left) ───────────────────────────────────────
    fold_points = [
        (x, y + h),
        (x + fold_size, y + h),
        (x, y + h + fold_size),
    ]
    rd.polygon(fold_points, fill=fold_color)

    result = Image.alpha_composite(result, ribbon_layer)
    return result



# ─────────────────────────────────────────────────────────────────────────────
# BorderFrame
# ─────────────────────────────────────────────────────────────────────────────

def border_frame(
    base: Image.Image,
    region: Tuple[int, int, int, int],  # (x, y, w, h)
    border_color: RGBA = (255, 255, 255, 200),
    border_width: int = 3,
    radius: int = 12,
    glow_color: RGBA = (255, 255, 255, 40),
    glow_radius: int = 6,
    fill_color: Optional[RGBA] = None,
) -> Image.Image:
    """
    Thin decorative border with subtle outer glow.

    Ideal for: elegant headline framing, feature callouts.
    """
    x, y, w, h = region
    # Robust normalization
    border_color = _norm_color(border_color)
    glow_color = _norm_color(glow_color)
    if fill_color:
        fill_color = _norm_color(fill_color)
    
    radius = int(radius)
    border_width = int(border_width)
    glow_radius = int(glow_radius)

    result = base.convert("RGBA")

    # ── Glow ──────────────────────────────────────────────────────────────
    if glow_color[3] > 0 and glow_radius > 0:
        glow_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.rounded_rectangle(
            [x, y, x + w, y + h],
            radius=radius,
            outline=glow_color,
            width=border_width + glow_radius,
        )
        glow_layer = glow_layer.filter(
            ImageFilter.GaussianBlur(radius=glow_radius)
        )
        result = Image.alpha_composite(result, glow_layer)

    # ── Optional fill ─────────────────────────────────────────────────────
    if fill_color and fill_color[3] > 0:
        fill_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        fd = ImageDraw.Draw(fill_layer)
        fd.rounded_rectangle(
            [x, y, x + w, y + h], radius=radius, fill=fill_color
        )
        result = Image.alpha_composite(result, fill_layer)

    # ── Border ────────────────────────────────────────────────────────────
    border_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(border_layer)
    bd.rounded_rectangle(
        [x, y, x + w, y + h],
        radius=radius,
        outline=border_color,
        width=border_width,
    )
    result = Image.alpha_composite(result, border_layer)

    return result



# ─────────────────────────────────────────────────────────────────────────────
# PillBadge
# ─────────────────────────────────────────────────────────────────────────────

def pill_badge(
    base: Image.Image,
    region: Tuple[int, int, int, int],  # (x, y, w, h)
    fill_color: RGBA = (237, 28, 36, 255),
    border_color: RGBA = (255, 255, 255, 220),
    border_width: int = 2,
    shadow_offset: Tuple[int, int] = (2, 3),
    shadow_blur: int = 5,
    shadow_color: RGBA = (0, 0, 0, 100),
) -> Image.Image:
    """
    Capsule/pill shaped badge (fully rounded ends).

    Ideal for: price tags (৳৪৯), data amounts (3GB), small labels.
    """
    x, y, w, h = region
    radius = int(h // 2)

    # Normalize colors and types
    fill_color = _norm_color(fill_color)
    border_color = _norm_color(border_color)
    shadow_color = _norm_color(shadow_color)
    border_width = int(border_width)
    shadow_blur = int(shadow_blur)
    shadow_offset = (int(shadow_offset[0]), int(shadow_offset[1]))

    result = base.convert("RGBA")

    # Shadow
    if shadow_color[3] > 0:
        shadow_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        sd.rounded_rectangle(
            [
                x + shadow_offset[0],
                y + shadow_offset[1],
                x + w + shadow_offset[0],
                y + h + shadow_offset[1],
            ],
            radius=radius,
            fill=shadow_color,
        )
        if shadow_blur > 0:
            shadow_layer = shadow_layer.filter(
                ImageFilter.GaussianBlur(radius=shadow_blur)
            )
        result = Image.alpha_composite(result, shadow_layer)

    # Fill
    badge_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge_layer)
    bd.rounded_rectangle(
        [x, y, x + w, y + h], radius=radius, fill=fill_color
    )

    # Border
    if border_width > 0 and border_color[3] > 0:
        bd.rounded_rectangle(
            [x, y, x + w, y + h],
            radius=radius,
            outline=border_color,
            width=border_width,
        )

    result = Image.alpha_composite(result, badge_layer)
    return result



# ─────────────────────────────────────────────────────────────────────────────
# AccentStrip
# ─────────────────────────────────────────────────────────────────────────────

def accent_strip(
    base: Image.Image,
    position: Tuple[int, int],  # (x, y) top-left of the strip
    width: int = 200,
    height: int = 4,
    color: RGBA = (253, 196, 0, 255),
    radius: int = 2,
) -> Image.Image:
    """
    Thin accent color bar for visual separation and emphasis.
    """
    x, y = int(position[0]), int(position[1])
    width, height = int(width), int(height)
    radius = int(radius)
    color = _norm_color(color)
    
    result = base.convert("RGBA")
    strip_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip_layer)
    sd.rounded_rectangle(
        [x, y, x + width, y + height],
        radius=radius,
        fill=color,
    )
    result = Image.alpha_composite(result, strip_layer)
    return result



# ─────────────────────────────────────────────────────────────────────────────
# Full-panel gradient overlay (for sidebar/bottom readability)
# ─────────────────────────────────────────────────────────────────────────────

def gradient_overlay(
    base: Image.Image,
    side: str = "left",
    coverage: float = 0.4,
    color: RGBA = (0, 0, 0, 210),
) -> Image.Image:
    """
    Apply a smooth gradient overlay on one side of the image.
    """
    W, H = base.size
    result = base.convert("RGBA")
    color = _norm_color(color)

    if side in ("left", "right"):
        grad_w = int(W * coverage)
        arr = np.zeros((H, grad_w, 4), dtype=np.uint8)
        t = np.linspace(1.0, 0.0, grad_w, dtype=np.float32)
        if side == "right":
            t = t[::-1]
        for c in range(4): # Loop through RGBA
            arr[:, :, c] = int(color[c])
        # Apply gradient to alpha channel
        arr[:, :, 3] = (t * color[3]).astype(np.uint8)
        
        gradient_img = Image.fromarray(arr, "RGBA")
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        paste_x = 0 if side == "left" else W - grad_w
        overlay.paste(gradient_img, (paste_x, 0))


    elif side in ("bottom", "top"):
        grad_h = int(H * coverage)
        arr = np.zeros((grad_h, W, 4), dtype=np.uint8)
        t = np.linspace(0.0, 1.0, grad_h, dtype=np.float32)
        if side == "top":
            t = t[::-1]
        for c in range(3):
            arr[:, :, c] = int(color[c])
        arr[:, :, 3] = (t[:, np.newaxis] * color[3]).astype(np.uint8)
        gradient_img = Image.fromarray(arr, "RGBA")
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        paste_y = H - grad_h if side == "bottom" else 0
        overlay.paste(gradient_img, (0, paste_y))

    else:
        return result

    return Image.alpha_composite(result, overlay)
