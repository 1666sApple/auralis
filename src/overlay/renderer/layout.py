"""
renderer/layout.py
==================
Places text blocks onto images. Supports:
  - Rich text blocks (multi-color inline segments)
  - 100% Strict Safe Zone bounding (avoids subject dynamically)
  - Overlap avoidance
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, List

from PIL import Image

from src.overlay.renderer.font_engine import (
    RenderParams, UnifiedRenderer, TextSegment,
    PANGO_ALIGN_LEFT, PANGO_ALIGN_CENTER, PANGO_ALIGN_RIGHT,
)
from src.overlay.layout.dead_space import SafeZone


# ─────────────────────────────────────────────────────────────────────────────
# Anchor points
# ─────────────────────────────────────────────────────────────────────────────

class AnchorPoint(Enum):
    TOP_LEFT    = "top_left"
    TOP_CENTER  = "top_center"
    TOP_RIGHT   = "top_right"
    MID_LEFT    = "mid_left"
    CENTER      = "center"
    MID_RIGHT   = "mid_right"
    BOT_LEFT    = "bot_left"
    BOT_CENTER  = "bot_center"
    BOT_RIGHT   = "bot_right"


# ─────────────────────────────────────────────────────────────────────────────
# TextBlock — legacy single-color text
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TextBlock:
    text: str
    params: RenderParams
    anchor: AnchorPoint = AnchorPoint.TOP_LEFT
    zone_index: int = 0
    margin_px: int = 12
    max_width_fraction: float = 0.85
    bg_box: bool = False
    bg_color: Tuple[int, int, int, int] = (0, 0, 0, 160)
    bg_radius: int = 12
    bg_padding: int = 12
    container: Optional[str] = None
    container_kwargs: dict = field(default_factory=dict)
    stack_below: bool = False
    min_font_size: int = 18
    fixed_position: Optional[Tuple[int, int]] = None
    group_id: str = "default"  # To group related blocks in the same safe zone


# ─────────────────────────────────────────────────────────────────────────────
# RichTextBlock — multi-color inline segments
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RichTextBlock:
    segments: List[TextSegment]
    params: RenderParams
    anchor: AnchorPoint = AnchorPoint.TOP_LEFT
    fixed_position: Optional[Tuple[int, int]] = None
    margin_px: int = 12
    min_font_size: int = 22
    bg_padding: int = 12
    container: Optional[str] = None
    container_kwargs: dict = field(default_factory=dict)
    group_id: str = "default"



# ─────────────────────────────────────────────────────────────────────────────
# Overlap detection & avoidance
# ─────────────────────────────────────────────────────────────────────────────

def _rects_overlap(r1, r2):
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2
    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)

def _shift_to_avoid(rect, placed, max_attempts=8):
    x, y, w, h = rect
    for _ in range(max_attempts):
        overlap = False
        for pr in placed:
            if _rects_overlap((x, y, w, h), pr):
                overlap = True
                _, py, _, ph = pr
                y = py + ph + 8  # shift down
                break
        if not overlap:
            break
    return x, y


# ─────────────────────────────────────────────────────────────────────────────
# LayoutEngine
# ─────────────────────────────────────────────────────────────────────────────

class LayoutEngine:
    def __init__(self, renderer: UnifiedRenderer):
        self._renderer = renderer

    def apply(
        self,
        base: Image.Image,
        blocks: list,
        safe_zones: list = None,
        margin_pct: float = 0.02,
    ) -> Image.Image:
        result = base.convert("RGBA")
        W, H = result.size
        placed_boxes = []
        safe_zones = safe_zones or []

        # 1. Pre-calculate all block sizes and scales
        rendered_data = []
        group_stats = {} # group_id -> {"total_h": float, "placed_h": float, "count": int}

        for block in blocks:
            # 1a. Identify best safe zone
            best_zone = None
            if safe_zones and not getattr(block, "fixed_position", None):
                best_zone = self._find_best_zone(block.anchor, safe_zones, W, H, block.margin_px)

            min_edge_gap = 15
            margin = max(block.margin_px, int(W * 0.05), min_edge_gap)

            if best_zone:
                zx, zy, zw, zh = best_zone.rect
                allowed_w = max(zw - (margin * 2), int(W * 0.35))
                block.params.max_width_px = min(block.params.max_width_px or 9999, allowed_w)

            # 1b. Iterative scaling
            min_size = getattr(block, "min_font_size", 18)
            text_img = None
            while block.params.font_size >= min_size:
                if isinstance(block, RichTextBlock):
                    text_img = self._renderer.render_rich(block.segments, block.params)
                else:
                    if not block.text or not block.text.strip(): break
                    text_img = self._renderer.render(block.text, block.params)

                if text_img is None: break
                tw, th = text_img.size
                if not best_zone: break
                _, _, _, zh_zone = best_zone.rect
                
                # POPPY ENLARGER FIX: 
                # If the block contains enlarged segments (> 1.2), we allow it to
                # exceed the zone height by up to 40% if vertically centered.
                is_poppy = any(getattr(seg, 'scale', 1.0) > 1.1 for seg in getattr(block, 'segments', []))
                height_limit = (zh_zone - (margin * 2))
                if is_poppy:
                    height_limit *= 1.4 # Be more lenient for poppy blocks
                
                if th <= height_limit: break

                
                new_size = int(block.params.font_size * 0.85)
                if new_size == block.params.font_size: break
                block.params.font_size = new_size

            if text_img:
                tw, th = text_img.size
                rendered_data.append({
                    "block": block,
                    "img": text_img,
                    "zone": best_zone,
                    "margin": margin
                })
                
                # 2. Group height analysis (Running update)
                gid = block.group_id
                stat = group_stats.get(gid, {"total_h": 0, "placed_h": 0, "count": 0})
                spacing = 15 # Padding between blocks in a group
                if stat["count"] > 0:
                    stat["total_h"] += spacing
                stat["total_h"] += th
                stat["count"] += 1
                group_stats[gid] = stat

        # 3. Final placement
        for item in rendered_data:
            block = item["block"]
            text_img = item["img"]
            best_zone = item["zone"]
            margin = item["margin"]
            tw, th = text_img.size
            gid = block.group_id
            
            if best_zone:
                zx, zy, zw, zh = best_zone.rect
                ix, iy = self._anchor_pos(block.anchor, tw, th, zw, zh, margin)
                px = zx + ix
                
                # Group-based Vertical Centering
                midline_anchors = (AnchorPoint.MID_LEFT, AnchorPoint.CENTER, AnchorPoint.MID_RIGHT)
                if block.anchor in midline_anchors:
                    total_gh = group_stats[gid]["total_h"]
                    # Base Y is image center minus half of TOTAL GROUP height
                    group_start_y = (H - total_gh) // 2
                    py = int(group_start_y + group_stats[gid]["placed_h"])
                else:
                    py = zy + iy
            elif getattr(block, "fixed_position", None):
                px, py = block.fixed_position
            else:
                px, py = self._anchor_pos(block.anchor, tw, th, W, H, margin)

            # Update placed height for next item in group (before shift_to_avoid)
            group_stats[gid]["placed_h"] += th + 15

            # 4. Strict Edge Clamp
            min_edge = 15
            px = max(min_edge, min(px, W - tw - min_edge))
            py = max(min_edge, min(py, H - th - min_edge))

            # Optional container rendering with Locked-Shift support
            dx, dy = 0, 0
            if getattr(block, "container", None):
                result, dx, dy = self._apply_container(
                    result, block.container,
                    px, py, tw, th,
                    block.bg_padding, block.container_kwargs,
                )

            # Composite (applying the container's dx/dy to the text position)
            px_shifted, py_shifted = px + dx, py + dy
            clip_w, clip_h = min(tw, W - px_shifted), min(th, H - py_shifted)
            if clip_w > 0 and clip_h > 0:
                text_clipped = text_img.crop((0, 0, clip_w, clip_h))
                result.paste(text_clipped, (px_shifted, py_shifted), text_clipped)
                placed_boxes.append((px_shifted, py_shifted, tw, th))


        return result


    def _find_best_zone(self, anchor, safe_zones: List[SafeZone], W, H, margin):
        """
        Find the safe zone using a weighted score of:
          - Safety (how empty it is)
          - Distance to ideal anchor position (with vertical center bonus)
        """
        tx, ty = self._anchor_pos(anchor, 0, 0, W, H, margin)
        best_zone = None
        best_score = -1.0
        
        # Target y is vertical center (User request): H/2
        target_y = H / 2
        
        # Max possible distance squared (diagonal)
        max_dist_sq = W**2 + H**2
        
        for z in safe_zones:
            zx, zy, zw, zh = z.rect
            # Calculate distance from ideal point to the center of the zone
            cx = zx + zw / 2
            cy = zy + zh / 2
            dist_sq = (cx - tx)**2 + (cy - ty)**2
            
            # Vertical centering priority: distance from cy to H/2
            v_dist_ratio = 1.0 - (abs(cy - target_y) / (H / 2))
            
            # Proximity to anchor (horizontal/general)
            proximity = 1.0 - (dist_sq / max_dist_sq)
            
            safety_val = z.safety_score
            if safety_val < 0.95:
                # Still respect major subjects, but less restrictive for centering
                safety_val *= 0.7  
            
            import random
            # Vertical Strike Bonus: Does the zone actually cross the midline? (User request 2026-03-31)
            is_centered_v = (zy <= target_y <= zy + zh)
            v_strike_bonus = 1.0 if is_centered_v else 0.0
            
            # Weighted Score
            # Vertical alignment and the "Midline Strike" are absolute priorities.
            score = (v_dist_ratio * 0.60) + v_strike_bonus
            
            # STICK TO THE LEFT (User request 2026-03-31: "Central left")
            # Penalize the entire right half of the image
            if (zx + zw/2) > W / 2:
                score *= 0.05
            
            # Small random jitter for variety
            score += random.uniform(0, 0.01)
            score *= 0.3  # Penalize right side heavily
            
            # STRICT penalty for zones touching corners/edges (Forbidden Zones)
            # We want to avoid the "Very edge" (User request 2026-03-31)
            edge_limit = 35 
            is_near_edge = (zx < edge_limit or (zx + zw) > W - edge_limit or 
                            zy < edge_limit or (zy + zh) > H - edge_limit)
            
            if is_near_edge:
                score *= 0.1  # Near-zero priority for edges
            
            if score > best_score:
                best_score = score
                best_zone = z
                
        return best_zone

    @staticmethod
    def _anchor_pos(anchor, tw, th, W, H, margin):
        if anchor in (AnchorPoint.TOP_LEFT, AnchorPoint.MID_LEFT, AnchorPoint.BOT_LEFT):
            x = margin
        elif anchor in (AnchorPoint.TOP_CENTER, AnchorPoint.CENTER, AnchorPoint.BOT_CENTER):
            x = (W - tw) // 2
        else:
            x = W - tw - margin

        if anchor in (AnchorPoint.TOP_LEFT, AnchorPoint.TOP_CENTER, AnchorPoint.TOP_RIGHT):
            y = margin
        elif anchor in (AnchorPoint.MID_LEFT, AnchorPoint.CENTER, AnchorPoint.MID_RIGHT):
            y = (H - th) // 2
        else:
            y = H - th - margin

        return (int(max(x, 0)), int(max(y, 0)))

    @staticmethod
    def _apply_container(image, container_type, x, y, tw, th, padding, kwargs):
        from src.overlay.renderer.containers import (
            gradient_badge, frosted_panel, ribbon_banner,
            border_frame, pill_badge,
        )
        W, H = image.size
        
        # 1. Padding Logic: INCREASED to 4x for premium look (User Request 03:34)
        h_pad = int(padding * 4) if container_type == "pill" else padding
        v_pad = padding

        
        # 2. Initial Region
        rx = x - h_pad
        ry = y - v_pad
        rw = tw + h_pad * 2
        rh = th + v_pad * 2

        # 3. Clamping and Shift Calculation
        # Target position is (rx, ry). Final position is (rx_final, ry_final).
        # The shift (dx, dy) is the difference that the text must also follow.
        rx_final = int(max(10, min(rx, W - rw - 10)))
        ry_final = int(max(10, min(ry, H - rh - 10)))
        
        dx = rx_final - rx
        dy = ry_final - ry
        
        # Final dimensions (limited to canvas)
        rw_final = int(min(rw, W - rx_final - 10))
        rh_final = int(min(rh, H - ry_final - 10))
        
        region = (rx_final, ry_final, rw_final, rh_final)

        dispatch = {
            "gradient_badge": gradient_badge,
            "frosted_panel": frosted_panel,
            "ribbon": ribbon_banner,
            "border_frame": border_frame,
            "pill": pill_badge,
        }
        fn = dispatch.get(container_type)
        if fn:
            image = fn(image, region, **kwargs)
            
        return image, dx, dy



