"""
renderer/font_engine.py
=======================
Cross-platform text rendering engine for Bengali + English.

APPROACH:
  Pillow 12+ with libraqm handles Bengali OpenType shaping natively.
  No GTK3, no libpango, no pycairo dependencies required.

  For Bengali: uses proper Unicode fonts (Galada, NotoSansBengali, HindSiliguri)
  For English: uses Tondo brand fonts

FONT MANAGEMENT:
  Auto-downloads open-source Bengali fonts from Google Fonts on first run.
  Caches them locally for subsequent use.
"""

from __future__ import annotations

import os
import platform
import sys
import socket
import tempfile
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ─────────────────────────────────────────────────────────────────────────────
# Backend detection
# ─────────────────────────────────────────────────────────────────────────────

try:
    from PIL import features as _pil_features
    HAS_RAQM = _pil_features.check_feature("raqm")
except Exception:
    HAS_RAQM = False

if not HAS_RAQM:
    import warnings
    warnings.warn(
        "[font_engine] Pillow does NOT have libraqm support. "
        "Bengali text shaping may be broken. "
        "Install libraqm: pip install Pillow --upgrade",
        RuntimeWarning,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

BENGALI_RANGE = (0x0980, 0x09FF)

# Alignment constants (backward-compatible with old Pango constants)
PANGO_ALIGN_LEFT = 0
PANGO_ALIGN_CENTER = 1
PANGO_ALIGN_RIGHT = 2


def needs_complex_shaping(text: str) -> bool:
    """Return True if any character requires complex shaping (Bengali)."""
    for ch in text:
        cp = ord(ch)
        if BENGALI_RANGE[0] <= cp <= BENGALI_RANGE[1]:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Google Fonts download URLs
# ─────────────────────────────────────────────────────────────────────────────

GOOGLE_FONT_URLS = {
    # Modern sans — elegant body text
    "NotoSansBengali-Regular": (
        "https://github.com/google/fonts/raw/main/"
        "ofl/notosansbengali/static/NotoSansBengali-Regular.ttf"
    ),
    # UI-friendly — CTA buttons, small text
    "HindSiliguri-Regular": (
        "https://raw.githubusercontent.com/google/fonts/main/"
        "ofl/hindsiliguri/HindSiliguri-Regular.ttf"
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# FontManager — downloads & caches open-source Bengali fonts
# ─────────────────────────────────────────────────────────────────────────────

class FontManager:
    """
    Manages font files: scans local directories and auto-downloads
    open-source Bengali fonts from Google Fonts on first run.

    Usage:
        fm = FontManager(custom_font_dir=Path("assets/fonts"))
        fm.ensure_google_fonts()
        path = fm.get_path("Galada-Regular")
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        custom_font_dir: Optional[Path] = None,
    ):
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / "_ad_pipeline_fonts"
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._custom_dir = custom_font_dir
        self._font_paths: dict[str, Path] = {}
        self._scan_custom_fonts()

    def _scan_custom_fonts(self):
        """Register custom fonts from the configured directory."""
        if self._custom_dir and self._custom_dir.exists():
            for ext in ("*.ttf", "*.otf", "*.TTF", "*.OTF"):
                for fp in self._custom_dir.glob(ext):
                    self._font_paths[fp.stem] = fp

    def ensure_google_fonts(self, timeout: int = 10):
        """Download Google Fonts if not already cached. Uses timeout of 10s."""
        for name, url in GOOGLE_FONT_URLS.items():
            target = self._cache_dir / f"{name}.ttf"
            if target.exists():
                self._font_paths[name] = target
                continue

            try:
                print(f"  ⬇ Downloading font: {name}...")
                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (AdPipeline)'}
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    with open(target, 'wb') as f:
                        f.write(response.read())
                
                self._font_paths[name] = target
                print(f"  ✓ Cached: {target.name}")
            except (urllib.error.URLError, socket.timeout, Exception) as e:
                print(f"  ✗ Font download failed ({name}): {e}")
                # If download failed, check if we have it in ANY font dir already
                # (maybe it was manually copied but not in cache)
                if name in self._font_paths:
                    print(f"  ℹ Using fallback already in registry for {name}")
                else:
                    # Final attempt: search custom dir specifically
                    self._scan_custom_fonts()
                    if name in self._font_paths:
                         print(f"  ℹ Found in custom font dir: {name}")

    def get_path(self, family: str) -> Optional[Path]:
        """
        Get path for a font family name.
        Tries exact match first, then case-insensitive fuzzy match.
        """
        if family in self._font_paths:
            return self._font_paths[family]

        # Fuzzy match: normalize separators and case
        norm = family.lower().replace(" ", "").replace("-", "").replace("_", "")
        for name, path in self._font_paths.items():
            candidate = name.lower().replace(" ", "").replace("-", "").replace("_", "")
            if candidate == norm:
                return path
        return None

    def get_bengali_font(self, style: str = "headline") -> Optional[Path]:
        """
        Get the best available Unicode Bengali font for a given role.

        Roles: "headline", "subline", "cta", "body"
        """
        priority_map = {
            "headline": [
                "Shorif Bongobondhu UNICODE",
                "Li Azad Feni Unicode",
                "HindSiliguri-Regular",
                "NotoSansBengali-Regular",
            ],
            "subline": [
                "HindSiliguri-Regular",
                "Li Azad Feni Unicode",
                "NotoSansBengali-Regular",
            ],
            "cta": [
                "Li Azad Feni Unicode",
                "HindSiliguri-Regular",
            ],
            "body": [
                "HindSiliguri-Regular",
                "NotoSansBengali-Regular",
            ],
        }

        candidates = priority_map.get(style, priority_map["body"])
        for name in candidates:
            p = self.get_path(name)
            if p and p.exists():
                return p

        # Ultimate fallback: any Bengali font we have
        for name in [
            "NotoSansBengali-Regular",
            "HindSiliguri-Regular",
        ]:
            p = self.get_path(name)
            if p and p.exists():
                return p

        return None

    def list_registered(self) -> dict[str, Path]:
        """Return all registered font names and paths."""
        return dict(self._font_paths)


# ─────────────────────────────────────────────────────────────────────────────
# FontRegistry — backward-compatible wrapper (no fontconfig needed)
# ─────────────────────────────────────────────────────────────────────────────

class FontRegistry:
    """
    Simplified font registry. Replaces the old fontconfig-based approach.
    No system dependencies required.

    Usage:
        registry = FontRegistry()
        registry.add_directory("assets/fonts")
        registry.activate()   # downloads Google Fonts
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self._manager = FontManager(cache_dir=cache_dir)
        self._activated = False

    def add(self, font_path: str | Path):
        p = Path(font_path)
        if p.exists():
            self._manager._font_paths[p.stem] = p

    def add_directory(self, directory: str | Path):
        d = Path(directory)
        if d.exists():
            for ext in ("*.ttf", "*.otf", "*.TTF", "*.OTF"):
                for fp in d.glob(ext):
                    self._manager._font_paths[fp.stem] = fp

    def activate(self):
        """Download Google Fonts and mark as ready."""
        self._manager.ensure_google_fonts()
        self._activated = True

    @property
    def manager(self) -> FontManager:
        return self._manager

    def list_families(self) -> list[str]:
        """Return registered font family names."""
        return list(self._manager._font_paths.keys())


# ─────────────────────────────────────────────────────────────────────────────
# TextMetrics
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TextMetrics:
    width: float
    height: float
    line_count: int = 1


# ─────────────────────────────────────────────────────────────────────────────
# TextSegment — for inline multi-color rich text
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TextSegment:
    """
    A colored segment of text within a rich headline.

    Used for inline highlights:
      [TextSegment("৩ জিবি", YELLOW), TextSegment("মাত্র", WHITE), ...]
    """
    text: str
    color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    scale: float = 1.0  # relative to base font_size (1.2 = 20% larger)
    stroke_color: Optional[Tuple[float, float, float, float]] = None
    stroke_width: Optional[float] = None
    stroke2_color: Optional[Tuple[float, float, float, float]] = None
    stroke2_width: Optional[float] = None
    highlight: bool = False



# ─────────────────────────────────────────────────────────────────────────────
# RenderParams
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RenderParams:
    """
    Full text rendering specification.

    Colors are RGBA floats (0.0–1.0).
    font_family should match a registered font name (stem of .ttf file).
    """
    font_family: str = "Li Azad Feni Unicode"
    font_size: int = 48
    bold: bool = False
    italic: bool = False
    color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    stroke_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    stroke_width: float = 3.0
    stroke2_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    stroke2_width: float = 0.0
    shadow_offset: Tuple[int, int] = (3, 3)
    shadow_blur: int = 6
    shadow_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.7)
    max_width_px: Optional[int] = None
    align: int = PANGO_ALIGN_LEFT
    line_spacing_px: int = 4
    padding: int = 8


# ─────────────────────────────────────────────────────────────────────────────
# Random font picker
# ─────────────────────────────────────────────────────────────────────────────

import random

# Fonts known to correctly render Unicode Bengali
_UNICODE_FONT_NAMES = {
    "FN-Bhorer-Alo-2-Unicode(1)",
    "Li Azad Feni Unicode",
    "Shorif Bongobondhu UNICODE",
}


def pick_random_font(
    font_manager: "FontManager",
    new_fonts_dir: Optional[Path] = None,
    prefer_unicode: bool = True,
) -> str:
    """
    Pick a random font family name from available fonts.

    If new_fonts_dir is given, registers those fonts first.
    Returns the font family name (stem).
    """
    if new_fonts_dir and new_fonts_dir.exists():
        for ext in ("*.ttf", "*.otf"):
            for fp in new_fonts_dir.glob(ext):
                font_manager._font_paths[fp.stem] = fp

    all_fonts = list(font_manager._font_paths.keys())

    if prefer_unicode:
        # Prefer Unicode-safe fonts
        unicode_fonts = [
            f for f in all_fonts
            if any(u.lower() in f.lower() for u in ("unicode", "bhorer", "bongobondhu", "azad"))
        ]
        # Also include Google-downloaded fonts (Excluding Galada)
        google_fonts = [
            f for f in all_fonts
            if any(g in f for g in ("NotoSans", "HindSiliguri"))
        ]
        candidates = [
            f for f in (unicode_fonts + google_fonts)
            if not any(w in f for w in ("Bold", "SemiBold", "Italic", "Medium", "Black", "Light", "ExtraBold", "ExtraLight"))
        ]
        if candidates:
            return random.choice(candidates)

    if all_fonts:
        return random.choice(all_fonts)

    return "NotoSansBengali-Bold"


# ─────────────────────────────────────────────────────────────────────────────
# UnifiedRenderer — single API for Bengali + English text
# ─────────────────────────────────────────────────────────────────────────────

class UnifiedRenderer:
    """
    Cross-platform text renderer. Handles Bengali (complex shaping) and
    English (Latin) text with a single API.

    Uses Pillow + libraqm for Bengali OpenType shaping.
    Automatically selects the correct Unicode font for Bengali text.

    Usage:
        fm = FontManager(custom_font_dir=Path("assets/fonts"))
        fm.ensure_google_fonts()
        renderer = UnifiedRenderer(font_manager=fm)
        img = renderer.render("মাত্র ৳৪৯ টাকায় ৩ জিবি!", params)
    """

    def __init__(
        self,
        font_manager: Optional[FontManager] = None,
        latin_font_path: Optional[str] = None,
    ):
        self._fm = font_manager or FontManager()
        self._latin_font_path = latin_font_path
        self._font_cache: dict[tuple, ImageFont.FreeTypeFont] = {}

    # ── Font resolution ──────────────────────────────────────────────────

    def _get_font(self, font_path: str, size: int) -> ImageFont.FreeTypeFont:
        """Load and cache a TrueType font."""
        key = (font_path, size)
        if key not in self._font_cache:
            try:
                self._font_cache[key] = ImageFont.truetype(font_path, size)
            except Exception:
                self._font_cache[key] = ImageFont.load_default(size=size)
        return self._font_cache[key]

    def _resolve_font_path(self, params: RenderParams, text: str) -> str:
        """
        Resolve a font_family name to an actual .ttf file path.

        Priority:
        1. Exact match in FontManager registry
        2. For Bengali text: best available Unicode Bengali font
        3. Latin font path
        4. Pillow default
        """
        # Try registered font by family name
        path = self._fm.get_path(params.font_family)
        if path and path.exists():
            # Check if this font can actually render Bengali
            # (KongshoMJ is Bijoy-encoded, won't work for Unicode Bengali)
            if needs_complex_shaping(text) and self._is_bijoy_font(path):
                # Fall back to Unicode Bengali font
                bn_path = self._fm.get_bengali_font(
                    "headline" if params.bold else "body"
                )
                if bn_path:
                    return str(bn_path)
            return str(path)

        # For Bengali text, find a suitable font
        if needs_complex_shaping(text):
            bn_path = self._fm.get_bengali_font(
                "headline" if params.bold else "body"
            )
            if bn_path:
                return str(bn_path)

        # For Latin, use configured font
        if self._latin_font_path and Path(self._latin_font_path).exists():
            return self._latin_font_path

        return ""

    @staticmethod
    def _is_bijoy_font(font_path: Path) -> bool:
        """
        Heuristic: detect if a font is Bijoy-encoded (not Unicode Bengali).
        KongshoMJ and similar legacy fonts don't have Unicode Bengali glyphs.
        """
        bijoy_names = {"kongshomj", "shahid kongshomj", "shahidkongshomj"}
        stem = font_path.stem.lower().replace("-", " ").replace("_", " ")
        return any(b in stem for b in bijoy_names)

    # ── Text wrapping ────────────────────────────────────────────────────

    @staticmethod
    def _wrap_text(
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: Optional[int],
    ) -> List[str]:
        """
        Word-wrap text to fit within max_width pixels.
        Works correctly for Bengali text thanks to raqm shaping.
        """
        if max_width is None:
            return text.split("\n") or [""]

        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        lines: List[str] = []

        for paragraph in text.split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue

            current = ""
            for word in words:
                test = (current + " " + word).strip()
                bb = draw.textbbox((0, 0), test, font=font)
                test_width = bb[2] - bb[0]

                if test_width > max_width and current:
                    lines.append(current)
                    current = word
                else:
                    current = test

            if current:
                lines.append(current)

        return lines if lines else [""]

    # ── Measurement ──────────────────────────────────────────────────────

    def measure(self, text: str, params: RenderParams) -> TextMetrics:
        """Measure text dimensions without rendering."""
        font_path = self._resolve_font_path(params, text)
        font = self._get_font(font_path, params.font_size)
        lines = self._wrap_text(text, font, params.max_width_px)

        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)

        total_h = 0
        max_w = 0
        for i, line in enumerate(lines):
            bb = draw.textbbox((0, 0), line, font=font)
            w = bb[2] - bb[0]
            h = bb[3] - bb[1]
            max_w = max(max_w, w)
            total_h += h
            if i < len(lines) - 1:
                total_h += params.line_spacing_px

        return TextMetrics(
            width=float(max_w),
            height=float(total_h),
            line_count=len(lines),
        )

    # ── Rendering ────────────────────────────────────────────────────────

    def render(self, text: str, params: RenderParams) -> Image.Image:
        """
        Render text to a transparent RGBA PIL Image.

        Includes shadow, stroke, and text fill — all via Pillow.
        Bengali text is correctly shaped by libraqm.
        """
        font_path = self._resolve_font_path(params, text)
        font = self._get_font(font_path, params.font_size)
        lines = self._wrap_text(text, font, params.max_width_px)

        # ── 1. Measure each line ─────────────────────────────────────────
        dummy = Image.new("RGBA", (1, 1))
        draw_dummy = ImageDraw.Draw(dummy)

        line_metrics: List[Tuple[int, int, int, int]] = []  # (w, h, ascent_offset_x, ascent_offset_y)
        for line in lines:
            sw = int(params.stroke_width) if params.stroke_width > 0 else 0
            bb = draw_dummy.textbbox(
                (0, 0), line, font=font, stroke_width=sw
            )
            line_metrics.append((
                bb[2] - bb[0],  # width
                bb[3] - bb[1],  # height
                -bb[0],         # x offset (textbbox can return negative x)
                -bb[1],         # y offset (textbbox can return negative y)
            ))

        if not line_metrics:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        line_widths = [m[0] for m in line_metrics]
        line_heights = [m[1] for m in line_metrics]

        # ── 2. Compute canvas size ───────────────────────────────────────
        pad = params.padding
        shadow_dx, shadow_dy = params.shadow_offset
        shadow_extra = (
            max(abs(shadow_dx), abs(shadow_dy)) + params.shadow_blur * 2
        )

        content_w = max(line_widths) if line_widths else 1
        content_h = (
            sum(line_heights)
            + max(0, len(lines) - 1) * params.line_spacing_px
        )

        total_w = int(content_w + pad * 2 + shadow_extra + 8)
        total_h = int(content_h + pad * 2 + shadow_extra + 8)

        # ── 3. Shadow layer ──────────────────────────────────────────────
        canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))

        if params.shadow_color[3] > 0.01:
            shadow_layer = Image.new(
                "RGBA", (total_w, total_h), (0, 0, 0, 0)
            )
            shadow_draw = ImageDraw.Draw(shadow_layer)
            sr, sg, sb, sa = (int(c * 255) for c in params.shadow_color)

            y = pad
            for i, line in enumerate(lines):
                ax = self._align_x(
                    params.align, total_w, line_widths[i], pad
                )
                ox, oy = line_metrics[i][2], line_metrics[i][3]
                shadow_draw.text(
                    (ax + ox + shadow_dx, y + oy + shadow_dy),
                    line,
                    font=font,
                    fill=(sr, sg, sb, sa),
                )
                y += line_heights[i] + params.line_spacing_px

            if params.shadow_blur > 0:
                shadow_layer = shadow_layer.filter(
                    ImageFilter.GaussianBlur(radius=params.shadow_blur)
                )
            canvas = Image.alpha_composite(canvas, shadow_layer)

        # ── 4. Text layer (stroke + fill) ────────────────────────────────
        text_layer = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)

        cr, cg, cb, ca = (int(c * 255) for c in params.color)
        scr, scg, scb, sca = (int(c * 255) for c in params.stroke_color)

        y = pad
        for i, line in enumerate(lines):
            ax = self._align_x(params.align, total_w, line_widths[i], pad)
            ox, oy = line_metrics[i][2], line_metrics[i][3]
            pos = (ax + ox, y + oy)

            if params.stroke_width > 0 and params.stroke_color[3] > 0.01:
                draw.text(
                    pos,
                    line,
                    font=font,
                    fill=(cr, cg, cb, ca),
                    stroke_width=int(params.stroke_width),
                    stroke_fill=(scr, scg, scb, sca),
                )
            else:
                draw.text(pos, line, font=font, fill=(cr, cg, cb, ca))

            y += line_heights[i] + params.line_spacing_px

        canvas = Image.alpha_composite(canvas, text_layer)
        return canvas

    # ── Rich text rendering (multi-color inline) ────────────────────────────

    def render_rich(
        self,
        segments: List[TextSegment],
        params: RenderParams,
    ) -> Image.Image:
        """
        Render multiple TextSegments on the same canvas with different colors.

        Each segment's words flow left-to-right, wrapping when exceeding
        max_width_px. All segments share the same font and stroke, but get
        their own fill color.

        This enables inline highlights like:
          "৩ জিবি" (yellow) + "Internet মাত্র" (white) + "৪৯ টাকায়!" (yellow)
        """
        font_path = self._resolve_font_path(params, "".join(s.text for s in segments))
        base_font = self._get_font(font_path, params.font_size)
        max_w = params.max_width_px or 99999
        pad = params.padding
        sw = int(params.stroke_width) if params.stroke_width > 0 else 0

        dummy = Image.new("RGBA", (1, 1))
        draw_d = ImageDraw.Draw(dummy)

        # ── 1. Build word list with per-word colors/strokes ───────────
        word_items = []  # [(word, color, font, size, sc_rgba, sw1, s2_rgba, sw2, is_high)]
        for seg in segments:
            seg_size = max(1, int(params.font_size * seg.scale))
            seg_font = self._get_font(font_path, seg_size)
            seg_color = tuple(int(c * 255) for c in seg.color)
            
            # Use segment overrides or block defaults
            sc = seg.stroke_color if seg.stroke_color is not None else params.stroke_color
            sw = seg.stroke_width if seg.stroke_width is not None else params.stroke_width
            s2c = seg.stroke2_color if seg.stroke2_color is not None else params.stroke2_color
            s2w = seg.stroke2_width if seg.stroke2_width is not None else params.stroke2_width
            
            # CRITICAL: Scale stroke width with segment scale
            sw_scaled = int(sw * seg.scale) if sw else 0
            s2w_scaled = int(s2w * seg.scale) if s2w else 0
            
            sc_rgba = tuple(int(c * 255) for c in sc)
            s2_rgba = tuple(int(c * 255) for c in s2c)

            # Check for highlight flag (sticker effect)
            is_high = getattr(seg, "highlight", False)
            if is_high:
                seg_color = (255, 255, 255, 255) # White text on sticker

            parts = seg.text.split("\n")
            for i, part in enumerate(parts):
                if i > 0:
                    word_items.append(("\n", seg_color, seg_font, seg_size, sc_rgba, sw_scaled, s2_rgba, s2w_scaled, is_high))
                for word in part.split():
                    word_items.append((word, seg_color, seg_font, seg_size, sc_rgba, sw_scaled, s2_rgba, s2w_scaled, is_high))

        if not word_items:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        # ── 2. Layout words into lines ────────────────────────────────
        lines = []      # list of [(word, color, font, size, bb_w, bb_h, ox, oy, sc_rgba, sw1, s2_rgba, sw2, is_high)]
        current_line = []
        current_w = 0
        
        # Dynamic space width based on base font size
        space_w = int(params.font_size * 0.22)

        for word, color, font, size, sc_rgba, sw1, s2_rgba, sw2, is_high in word_items:
            if word == "\n":
                if current_line:
                    lines.append(current_line)
                    current_line = []
                    current_w = 0
                continue
                
            # Use stroke in calculation
            calc_sw = max(sw1, sw2)
            bb = draw_d.textbbox((0, 0), word, font=font, stroke_width=calc_sw)
            w = bb[2] - bb[0]
            h = bb[3] - bb[1]
            ox = -bb[0]
            oy = -bb[1]

            test_w = current_w + (space_w if current_line else 0) + w
            if test_w > max_w and current_line:
                lines.append(current_line)
                current_line = []
                current_w = 0

            current_line.append((word, color, font, size, w, h, ox, oy, sc_rgba, sw1, s2_rgba, sw2, is_high))
            current_w += (space_w if len(current_line) > 1 else 0) + w

        if current_line:
            lines.append(current_line)

        # ── 3. Compute canvas size ────────────────────────────────────
        line_heights = []
        line_widths = []
        for line in lines:
            lh = max(item[5] for item in line) if line else 0
            lw = sum(item[4] for item in line) + space_w * max(0, len(line) - 1)
            line_heights.append(lh)
            line_widths.append(lw)

        shadow_dx, shadow_dy = params.shadow_offset
        shadow_extra = max(abs(shadow_dx), abs(shadow_dy)) + params.shadow_blur * 2

        content_w = max(line_widths) if line_widths else 1
        content_h = sum(line_heights) + max(0, len(lines) - 1) * params.line_spacing_px

        total_w = int(content_w + pad * 2 + shadow_extra + 8)
        total_h = int(content_h + pad * 2 + shadow_extra + 8)

        # ── 4. Shadow layer ───────────────────────────────────────────
        canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))

        if params.shadow_color[3] > 0.01:
            shadow_layer = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
            sdraw = ImageDraw.Draw(shadow_layer)
            sr, sg, sb, sa = (int(c * 255) for c in params.shadow_color)

            y = pad
            for li, line in enumerate(lines):
                x = pad
                line_h = line_heights[li]
                for word, color, font, size, w, h, ox, oy, sc_rgba, sw1, s2_rgba, sw2, is_high in line:
                    sdraw.text(
                        (x + ox + shadow_dx, y + oy + shadow_dy + (line_h - h)),
                        word, font=font, fill=(sr, sg, sb, sa),
                    )
                    x += w + space_w
                y += line_heights[li] + params.line_spacing_px

            if params.shadow_blur > 0:
                shadow_layer = shadow_layer.filter(
                    ImageFilter.GaussianBlur(radius=params.shadow_blur)
                )
            canvas = Image.alpha_composite(canvas, shadow_layer)

        # ── 5. Text layer (Triple-pass for double border) ─────────────
        text_layer = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))

        tdraw = ImageDraw.Draw(text_layer)
        
        for pass_idx in range(3):
            y = pad
            for li, line in enumerate(lines):
                x = pad
                line_h = line_heights[li]
                for word, color, font, size, w, h, ox, oy, sc_rgba, sw1, s2_rgba, sw2, is_high in line:
                    pos = (x + ox, y + oy + (line_h - h))
                    
                    if pass_idx == 0 and sw2 > 0:
                        tdraw.text(pos, word, font=font, fill=(0, 0, 0, 0), stroke_width=int(sw2), stroke_fill=s2_rgba)
                    elif pass_idx == 1 and sw1 > 0:
                        tdraw.text(pos, word, font=font, fill=(0, 0, 0, 0), stroke_width=int(sw1), stroke_fill=sc_rgba)
                    elif pass_idx == 2:
                        tdraw.text(pos, word, font=font, fill=color)
                    
                    x += w + space_w
                y += line_heights[li] + params.line_spacing_px

        canvas = Image.alpha_composite(canvas, text_layer)
        return canvas

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _align_x(align: int, total_w: int, line_w: int, pad: int) -> int:
        """Compute x position for text alignment."""
        if align == PANGO_ALIGN_CENTER:
            return (total_w - line_w) // 2
        elif align == PANGO_ALIGN_RIGHT:
            return total_w - line_w - pad
        else:
            return pad


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compatibility aliases
# ─────────────────────────────────────────────────────────────────────────────

BengaliRenderer = UnifiedRenderer
LatinRenderer = UnifiedRenderer