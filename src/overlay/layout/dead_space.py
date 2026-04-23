"""
layout/dead_space.py
====================
"Dead Space Finder": locates image regions with low visual complexity
(safe for text overlay) without obscuring the hero subject.

Improvements over v1:
  - Coarser grid (3×4) → produces larger, more usable zones
  - Aggressive merge (2×2, 3×1, 1×3 blocks)
  - Subject mask: center 40% gets hard penalty
  - Minimum dimension constraint (25% of image width)
  - Returns zones ranked by both safety AND text fit capacity
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image


# ─────────────────────────────────────────────────────────────────────────────
# SafeZone
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SafeZone:
    x: int
    y: int
    w: int
    h: int
    safety_score: float   # 0.0 (complex/dangerous) → 1.0 (empty/safe)
    grid_row: int = 0
    grid_col: int = 0

    @property
    def rect(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    @property
    def area(self) -> int:
        return self.w * self.h

    def overlaps(self, other: "SafeZone", threshold: float = 0.3) -> bool:
        ix1 = max(self.x, other.x)
        iy1 = max(self.y, other.y)
        ix2 = min(self.x + self.w, other.x + other.w)
        iy2 = min(self.y + self.h, other.y + other.h)
        if ix2 <= ix1 or iy2 <= iy1:
            return False
        inter = (ix2 - ix1) * (iy2 - iy1)
        smaller = min(self.w * self.h, other.w * other.h)
        return inter / max(smaller, 1) > threshold


# ─────────────────────────────────────────────────────────────────────────────
# DeadSpaceConfig — tuned for ad text placement
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DeadSpaceConfig:
    grid_rows: int = 3            # Coarser → larger zones
    grid_cols: int = 4
    edge_weight: float = 0.55     # Edge density importance
    brightness_weight: float = 0.15
    center_penalty: float = 0.20  # Penalize hero (center) area more
    saturation_weight: float = 0.10  # High saturation = visually busy
    canny_low: int = 35
    canny_high: int = 110
    blur_kernel: int = 51
    min_safety_score: float = 0.25
    min_zone_width_pct: float = 0.20   # Min zone width as % of image
    min_zone_height_pct: float = 0.15  # Min zone height as % of image


class DeadSpaceFinder:
    """
    Analyses a PIL Image and returns ranked safe zones for text placement.

    Usage:
        finder = DeadSpaceFinder()
        zones = finder.find(image, top_k=6)
        best_rect = zones[0].rect  # (x, y, w, h)
    """

    def __init__(self, config: Optional[DeadSpaceConfig] = None):
        self.config = config or DeadSpaceConfig()

    def find(
        self,
        image: Image.Image,
        top_k: int = 6,
    ) -> List[SafeZone]:
        """Find the top-k safest zones for text placement."""
        img_rgb = np.array(image.convert("RGB"))
        H, W = img_rgb.shape[:2]
        cfg = self.config

        # ── 1. Edge density map ───────────────────────────────────────────
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, cfg.canny_low, cfg.canny_high)
        edge_density = cv2.GaussianBlur(
            edges.astype(np.float32),
            (cfg.blur_kernel, cfg.blur_kernel), 0
        )
        edge_density = edge_density / (edge_density.max() + 1e-6)

        # ── 2. Brightness penalty (extremes are bad for text) ─────────────
        brightness = gray.astype(np.float32) / 255.0
        brightness_score = 1.0 - np.abs(brightness - 0.5) * 2.0

        # ── 3. Center distance (penalize hero area) ───────────────────────
        cy, cx = H / 2, W / 2
        yy, xx = np.mgrid[0:H, 0:W]
        dist = np.sqrt(((xx - cx) / W) ** 2 + ((yy - cy) / H) ** 2)
        dist_norm = dist / (dist.max() + 1e-6)

        # ── 4. Subject mask: hard penalty on center 40% ──────────────────
        subject_mask = np.zeros((H, W), dtype=np.float32)
        margin_x = int(W * 0.30)
        margin_y = int(H * 0.20)
        subject_mask[margin_y:H - margin_y, margin_x:W - margin_x] = 1.0
        # Smooth the edges
        subject_mask = cv2.GaussianBlur(subject_mask, (51, 51), 0)

        # ── 5. Composite safety map ──────────────────────────────────────
        safety_map = (
            (1.0 - edge_density) * cfg.edge_weight
            + brightness_score * cfg.brightness_weight
            + dist_norm * cfg.center_penalty
            - subject_mask * 0.25  # Hard penalty for center region
        )
        safety_map = np.clip(safety_map, 0, 1)

        # ── 6. Grid scoring ──────────────────────────────────────────────
        cell_h = H // cfg.grid_rows
        cell_w = W // cfg.grid_cols
        zones: List[SafeZone] = []

        for r in range(cfg.grid_rows):
            for c in range(cfg.grid_cols):
                y1 = r * cell_h
                y2 = min((r + 1) * cell_h, H)
                x1 = c * cell_w
                x2 = min((c + 1) * cell_w, W)

                cell_safety = float(safety_map[y1:y2, x1:x2].mean())

                if cell_safety >= cfg.min_safety_score:
                    zones.append(SafeZone(
                        x=x1, y=y1, w=x2 - x1, h=y2 - y1,
                        safety_score=cell_safety,
                        grid_row=r, grid_col=c,
                    ))

        zones.sort(key=lambda z: z.safety_score, reverse=True)

        # ── 7. Aggressive merging ────────────────────────────────────────
        merged = self._merge_adjacent(
            zones, cfg.grid_rows, cfg.grid_cols, cell_h, cell_w
        )
        merged.sort(key=lambda z: z.safety_score, reverse=True)

        # ── 8. Filter by min dimensions ──────────────────────────────────
        min_w = int(W * cfg.min_zone_width_pct)
        min_h = int(H * cfg.min_zone_height_pct)
        filtered = [z for z in merged if z.w >= min_w and z.h >= min_h]

        # Fallback if nothing passes dimension filter
        if not filtered:
            filtered = self._fallback_zones(W, H)

        return filtered[:top_k]

    @staticmethod
    def _merge_adjacent(
        zones: List[SafeZone],
        grid_rows: int, grid_cols: int,
        cell_h: int, cell_w: int,
    ) -> List[SafeZone]:
        """
        Merge adjacent cells into larger rectangles.
        Supports 2×1, 1×2, 2×2, 3×1, 1×3 merges.
        """
        zone_map = {(z.grid_row, z.grid_col): z for z in zones}
        merged: List[SafeZone] = list(zones)

        for z in zones:
            r, c = z.grid_row, z.grid_col

            # 2×1 horizontal (right neighbor)
            right = zone_map.get((r, c + 1))
            if right:
                score = (z.safety_score + right.safety_score) / 2 * 0.95
                merged.append(SafeZone(
                    x=z.x, y=z.y,
                    w=z.w + right.w, h=z.h,
                    safety_score=score, grid_row=r, grid_col=c,
                ))

            # 1×2 vertical (bottom neighbor)
            below = zone_map.get((r + 1, c))
            if below:
                score = (z.safety_score + below.safety_score) / 2 * 0.95
                merged.append(SafeZone(
                    x=z.x, y=z.y,
                    w=z.w, h=z.h + below.h,
                    safety_score=score, grid_row=r, grid_col=c,
                ))

            # 2×2 block
            right = zone_map.get((r, c + 1))
            below = zone_map.get((r + 1, c))
            diag = zone_map.get((r + 1, c + 1))
            if right and below and diag:
                score = (
                    z.safety_score + right.safety_score
                    + below.safety_score + diag.safety_score
                ) / 4 * 0.90
                merged.append(SafeZone(
                    x=z.x, y=z.y,
                    w=z.w + right.w, h=z.h + below.h,
                    safety_score=score, grid_row=r, grid_col=c,
                ))

            # 3×1 horizontal
            r1 = zone_map.get((r, c + 1))
            r2 = zone_map.get((r, c + 2))
            if r1 and r2:
                score = (
                    z.safety_score + r1.safety_score + r2.safety_score
                ) / 3 * 0.88
                merged.append(SafeZone(
                    x=z.x, y=z.y,
                    w=z.w + r1.w + r2.w, h=z.h,
                    safety_score=score, grid_row=r, grid_col=c,
                ))

            # 1×3 vertical
            b1 = zone_map.get((r + 1, c))
            b2 = zone_map.get((r + 2, c))
            if b1 and b2:
                score = (
                    z.safety_score + b1.safety_score + b2.safety_score
                ) / 3 * 0.88
                merged.append(SafeZone(
                    x=z.x, y=z.y,
                    w=z.w, h=z.h + b1.h + b2.h,
                    safety_score=score, grid_row=r, grid_col=c,
                ))

        return merged

    @staticmethod
    def _fallback_zones(W: int, H: int) -> List[SafeZone]:
        """Generous corner/edge zones when nothing else is safe."""
        margin = int(min(W, H) * 0.03)
        half_w = W // 2
        third_h = H // 3

        return [
            # Left half, full height
            SafeZone(x=margin, y=margin, w=half_w - margin * 2,
                     h=H - margin * 2, safety_score=0.55),
            # Right half, full height
            SafeZone(x=half_w, y=margin, w=half_w - margin,
                     h=H - margin * 2, safety_score=0.50),
            # Top strip
            SafeZone(x=margin, y=margin, w=W - margin * 2,
                     h=third_h, safety_score=0.48),
            # Bottom strip
            SafeZone(x=margin, y=H - third_h - margin,
                     w=W - margin * 2, h=third_h, safety_score=0.45),
        ]

    def visualise(
        self, image: Image.Image, zones: List[SafeZone], top_n: int = 3
    ) -> Image.Image:
        """Draw coloured overlays on the image to visualise safe zones."""
        debug = image.convert("RGBA")
        draw_overlay = Image.new("RGBA", debug.size, (0, 0, 0, 0))

        import PIL.ImageDraw as ImageDraw
        draw = ImageDraw.Draw(draw_overlay)

        colors = [
            (0, 255, 0, 80),
            (255, 255, 0, 60),
            (0, 180, 255, 50),
        ]

        for i, zone in enumerate(zones[:top_n]):
            color = colors[min(i, len(colors) - 1)]
            draw.rectangle(
                [zone.x, zone.y, zone.x + zone.w, zone.y + zone.h],
                outline=(color[0], color[1], color[2], 200),
                width=3,
                fill=color,
            )

        result = Image.alpha_composite(debug, draw_overlay)
        return result.convert("RGB")
