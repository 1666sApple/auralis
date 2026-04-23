"""
templates/style_templates.py
============================
Airtel-style ad templates.

Design approach (matching user's reference):
  - ONE cohesive headline with INLINE color highlights
  - "৩ জিবি" in yellow, "৪৯ টাকায়" in golden — WITHIN the same text flow
  - NO background boxes/containers — thick text stroke = readability
  - Validity right BELOW headline, smaller, same stroke style
  - Disclaimer tiny at bottom edge
  - Random font from new fonts directory (1 font per banner)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing import Dict, List, Optional, Tuple

from src.overlay.renderer.font_engine import (
    RenderParams, TextSegment,
    PANGO_ALIGN_LEFT, PANGO_ALIGN_CENTER, PANGO_ALIGN_RIGHT,
    needs_complex_shaping
)

from src.overlay.renderer.layout import AnchorPoint, TextBlock, RichTextBlock
from src.overlay.renderer.effects import BrandPalette
from src.shared.utils.bijoy_converter import BijoyConverter



# ─────────────────────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AdTemplate:
    name: str
    aspect_w: int
    aspect_h: int
    brand: str = "airtel"
    vignette: float = 0.0
    gradient_bar: bool = False
    gradient_side: str = "left"
    gradient_coverage: float = 0.4


@dataclass
class OfferData:
    headline_bn: str = ""
    headline_en: str = ""
    subline_bn: str = ""
    subline_en: str = ""
    cta_bn: str = "Grab Now!"
    cta_en: str = "Grab Now!"
    price: str = ""
    data_gb: str = ""
    validity: str = ""
    brand: str = "airtel"
    lang: str = "bn"
    highlight_words: List[str] = field(default_factory=list)
    headline_segments: List[Dict] = field(default_factory=list)
    subline_segments: List[Dict] = field(default_factory=list)
    detail_segments: List[Dict] = field(default_factory=list)






# ─────────────────────────────────────────────────────────────────────────────
# Color constants (RGBA float 0-1)
# ─────────────────────────────────────────────────────────────────────────────

WHITE = (1.0, 1.0, 1.0, 1.0)
YELLOW = (253/255, 196/255, 0/255, 1.0)      # Airtel Golden Yellow
RED = (237/255, 28/255, 36/255, 1.0)          # Airtel Red
BLACK = (0.0, 0.0, 0.0, 1.0)
ORANGE = (242/255, 148/255, 0/255, 1.0)       # Airtel Orange
# Robi Colors
ROBI_ORANGE = (255/255, 102/255, 0/255, 1.0)
GOLD = (255/255, 191/255, 0/255, 1.0)




# ─────────────────────────────────────────────────────────────────────────────
# Disclaimers
# ─────────────────────────────────────────────────────────────────────────────

_DISC_BN = '"এয়ারটেল" রবি আক্সিয়াটা পিএলসি-এর একটি ব্র্যান্ড'
_DISC_BN_BIJOY = '"Gqvi‡Uj" we Avw·qvUv wcGjwm-Gi GKwU eª¨vÛ'
_DISC_EN = '"Airtel"- a brand of Robi Axiata PLC.'


# ─────────────────────────────────────────────────────────────────────────────
# Segment builder: parse headline into colored segments
# ─────────────────────────────────────────────────────────────────────────────

def apply_poppy_styling(segments_data: List[Dict], brand: str = "airtel") -> List[TextSegment]:
    """
    MODULAR POPPY COLORIZER: 
    Converts raw LLM segments into stylized TextSegments with 'poppy' colors.
    """
    brand = brand.lower()
    segments = []
    
    for seg in segments_data:
        if isinstance(seg, str):
            text = seg
            is_high = False
            scale = 1.0
        else:
            text = seg.get("text", "")
            is_high = seg.get("highlight", False)
            scale = seg.get("scale", 1.0)

        # BIJOY CONVERSION: Transform Unicode Bengali to Bijoy ASCII for KongshoMJ
        if needs_complex_shaping(text):
            text = BijoyConverter.convert(text)

        
        if is_high:
            if brand == "robi":
                segments.append(TextSegment(
                    text=text, color=WHITE, scale=scale,
                    stroke_color=ROBI_RED, stroke_width=4,
                    stroke2_color=ROBI_DARK, stroke2_width=8,
                    highlight=False
                ))
            else:
                # Airtel Poppy Palette: Differentiated Highlighting
                is_numeric = any(c.isdigit() or '\u09E6' <= c <= '\u09EF' for c in text)
                
                # Primary Enlarge (Offer Focus)
                if scale > 1.5 or is_numeric:
                    fill_color = YELLOW
                else:
                    # Hook word (Emotional Focus) - Migrated from Blue to White
                    fill_color = WHITE
                
                segments.append(TextSegment(
                    text=text, color=fill_color, scale=scale,
                    stroke_color=BLACK, stroke_width=5,
                    stroke2_color=RED, stroke2_width=10,
                    highlight=False # Stickers were removed
                ))



        else:
            # Standard high-readability style
            segments.append(TextSegment(
                text=text, color=WHITE, scale=scale,
                stroke_color=BLACK, stroke_width=5,
                highlight=False
            ))





            
    return segments

def _build_headline_segments(offer: OfferData, lang: str = "bn") -> List[TextSegment]:
    """
    Builds segments for the headline using Poppy Colorizer.
    """
    if offer.headline_segments:
        return apply_poppy_styling(offer.headline_segments, offer.brand)

    # Legacy Fallback
    headline = offer.headline_bn if lang in ("bn", "mixed") else offer.headline_en
    if not headline: return []
    
    fallback_data = []
    bn_word_nums = {"এক", "দুই", "তিন", "সাত", "দশ", "নয়", "আট", "ছয়", "পাঁচ", "চার"}
    for word in headline.split():
        clean = word.rstrip("!।,.")
        is_num = any(c.isdigit() or '\u09E6' <= c <= '\u09EF' for c in clean) or clean in bn_word_nums
        fallback_data.append({"text": word + " ", "highlight": is_num, "scale": 2.0 if is_num else 1.0})
        
    return apply_poppy_styling(fallback_data, offer.brand)

def _build_subline_segments(offer: OfferData, lang: str = "bn") -> List[TextSegment]:
    """
    Builds segments for the subline using Poppy Colorizer.
    """
    if offer.subline_segments:
        return apply_poppy_styling(offer.subline_segments, offer.brand)
        
    subline = offer.subline_bn if lang in ("bn", "mixed") else offer.subline_en
    if not subline: return []
    
    fallback_data = [{"text": subline, "highlight": False, "scale": 1.0}]
    return apply_poppy_styling(fallback_data, offer.brand)

def _build_detail_segments(offer: OfferData) -> List[TextSegment]:
    """
    Builds segments for the offer details (badge) using Poppy Colorizer.
    """
    if offer.detail_segments:
        return apply_poppy_styling(offer.detail_segments, offer.brand)
        
    details = []
    if offer.data_gb: details.append(offer.data_gb)
    if offer.price: details.append(offer.price)
    if offer.validity: details.append(offer.validity)
    
    if not details: return []
    
    fallback_data = []
    for i, text in enumerate(details):
        if i > 0: fallback_data.append({"text": "  |  ", "highlight": False, "scale": 1.0})
        for word in text.split():
            clean = word.rstrip("!।,.")
            is_num = any(c.isdigit() or '\u09E6' <= c <= '\u09EF' for c in clean) or clean in {"এক", "তিন", "সাত", "দশ"}
            fallback_data.append({"text": word + " ", "highlight": is_num, "scale": 1.75 if is_num else 1.0})
            
    return apply_poppy_styling(fallback_data, offer.brand)



# ═══════════════════════════════════════════════════════════════════════════════

# Template: Banner (1:1)
# ═══════════════════════════════════════════════════════════════════════════════

def make_banner_blocks(
    W: int, H: int,
    offer: OfferData,
    brand: str = "airtel",
    zone_index: int = 0,
    font_family: str = "KongshoMJ",
) -> list:

    lang = offer.lang
    blocks = []

    # ── 1. RICH HEADLINE
    segments = _build_headline_segments(offer, lang)
    if segments:
        # Increased from 0.09H to 0.12H (33% bigger)
        headline_size = max(int(H * 0.12), 45)
        blocks.append(RichTextBlock(

            segments=segments,
            params=RenderParams(
                font_family=font_family,
                font_size=headline_size,
                bold=False,
                color=WHITE,
                stroke_color=RED,
                stroke_width=max(4, int(H * 0.007)),
                shadow_offset=(4, 5),
                shadow_blur=10,
                shadow_color=(0.0, 0.0, 0.0, 0.8),
                max_width_px=int(W * 0.85),
                align=PANGO_ALIGN_LEFT,
                line_spacing_px=8,
                padding=10,
            ),
            anchor=AnchorPoint.MID_LEFT,
            group_id="offer",
            margin_px=20,
            min_font_size=28,
        ))

    # ── 2. VALIDITY (Subline)
    sub_segments = _build_subline_segments(offer, lang)
    if sub_segments:
        subline_size = int(headline_size * 0.40)
        blocks.append(RichTextBlock(
            segments=sub_segments,
            params=RenderParams(
                font_family=font_family,
                font_size=subline_size,
                bold=False, color=WHITE,
                stroke_color=RED, stroke_width=3,
                stroke2_color=BLACK, stroke2_width=6,
                shadow_offset=(2, 2), shadow_blur=5,
                shadow_color=(0.0, 0.0, 0.0, 0.6),
                max_width_px=int(W * 0.40),
                align=PANGO_ALIGN_LEFT,
                padding=6,
            ),
            anchor=AnchorPoint.MID_LEFT,
            group_id="offer",
            margin_px=20,
            min_font_size=20,
        ))


    # ── 3. OFFER DETAIL BADGE (Price, Data, Validity)
    detail_segments = _build_detail_segments(offer)
    if detail_segments:
        badge_size = int(headline_size * 0.40)
        blocks.append(RichTextBlock(
            segments=detail_segments,
            params=RenderParams(
                font_family=font_family,
                font_size=badge_size,
                bold=True, 
                stroke_color=BLACK, stroke_width=2,
                max_width_px=int(W * 0.90),
                align=PANGO_ALIGN_CENTER,
                padding=12,
            ),
            anchor=AnchorPoint.MID_LEFT,
            group_id="offer",
            container="pill",
            container_kwargs={
                "fill_color": (237, 28, 36, 255), # Branded Airtel Red
                "border_color": WHITE,
                "border_width": 2,
            },

            margin_px=20,
            min_font_size=24,
        ))



    # ── 4. LEGAL / DISCLAIMER
    disc = _DISC_BN if lang in ("bn", "mixed") else _DISC_EN
    disc_font = "KongshoMJ" if lang in ("bn", "mixed") else font_family
    if disc_font == "KongshoMJ":
        disc = _DISC_BN_BIJOY if lang in ("bn", "mixed") else _DISC_EN

    blocks.append(TextBlock(
        text=disc,
        params=RenderParams(
            font_family=disc_font,
            font_size=max(int(H * 0.016), 11),
            bold=False, color=(1.0, 1.0, 1.0, 0.65),
            stroke_color=(0.0, 0.0, 0.0, 0.4), stroke_width=1,
            max_width_px=int(W * 0.75), align=PANGO_ALIGN_LEFT, padding=2,
        ),
        anchor=AnchorPoint.BOT_LEFT,
        fixed_position=(int(W * 0.02), int(H * 0.945)),
        margin_px=0,
    ))

    return blocks


# ═══════════════════════════════════════════════════════════════════════════════
# Template: Headline
# ═══════════════════════════════════════════════════════════════════════════════

def make_headline_blocks(
    W: int, H: int,
    offer: OfferData,
    brand: str = "airtel",
    zone_index: int = 0,
    font_family: str = "KongshoMJ",
) -> list:

    lang = offer.lang
    blocks = []

    segments = _build_headline_segments(offer, lang)
    if segments:
        headline_size = max(int(H * 0.09), 40)
        blocks.append(RichTextBlock(
            segments=segments,
            params=RenderParams(
                font_family=font_family,
                font_size=headline_size,
                bold=False, color=WHITE,
                stroke_color=RED, stroke_width=max(6, int(H * 0.010)),
                shadow_offset=(5, 5), shadow_blur=5,
                shadow_color=(0.0, 0.0, 0.0, 0.8),
                max_width_px=int(W * 0.55), align=PANGO_ALIGN_LEFT,
                line_spacing_px=10, padding=12,
            ),
            anchor=AnchorPoint.MID_LEFT,
            group_id="offer",
            margin_px=20,
            min_font_size=28,
        ))

    validity_text = offer.subline_bn if lang in ("bn", "mixed") else offer.subline_en
    if validity_text:
        # BIJOY CONVERSION for standalone TextBlock
        if font_family == "KongshoMJ" and needs_complex_shaping(validity_text):
            validity_text = BijoyConverter.convert(validity_text)
            
        subline_size = int(headline_size * 0.40)
        blocks.append(TextBlock(
            text=validity_text,
            params=RenderParams(
                font_family=font_family, font_size=subline_size,
                bold=False, color=WHITE,
                stroke_color=RED, stroke_width=3,
                stroke2_color=BLACK, stroke2_width=6,
                shadow_offset=(2, 2), shadow_blur=4,
                shadow_color=(0.0, 0.0, 0.0, 0.5),
                max_width_px=int(W * 0.45), align=PANGO_ALIGN_LEFT, padding=6,
            ),
            anchor=AnchorPoint.MID_LEFT,
            group_id="offer",
            margin_px=20,
            min_font_size=30,
        ))

    # Offer Detail Badge
    details = []
    if offer.data_gb: details.append(offer.data_gb)
    if offer.price: details.append(offer.price)
    if offer.validity: details.append(offer.validity)
    
    if details:
        detail_text = "  |  ".join(details)
        # BIJOY CONVERSION for standalone TextBlock
        if font_family == "KongshoMJ" and needs_complex_shaping(detail_text):
            detail_text = BijoyConverter.convert(detail_text)
            
        badge_size = int(headline_size * 0.35)
        blocks.append(TextBlock(
            text=detail_text,
            params=RenderParams(
                font_family=font_family, font_size=badge_size,
                bold=True, color=WHITE,
                max_width_px=int(W * 0.50), align=PANGO_ALIGN_LEFT,
            ),
            anchor=AnchorPoint.MID_LEFT,
            group_id="offer",
            container="pill",
            container_kwargs={
                "fill_color": ROBI_RED if brand == "robi" else RED,
                "border_color": WHITE,
                "border_width": 2,
            },
            margin_px=20,
            min_font_size=24,
        ))

    # Disclaimer
    disc = _DISC_BN if lang in ("bn", "mixed") else _DISC_EN
    disc_font = "KongshoMJ" if lang in ("bn", "mixed") else font_family
    if disc_font == "ProjectMJ": disc = _DISC_BN_BIJOY
    
    blocks.append(TextBlock(
        text=disc,
        params=RenderParams(
            font_family=disc_font, font_size=max(int(H * 0.016), 11),
            bold=False, color=(1.0, 1.0, 1.0, 0.65),
            stroke_color=(0.0, 0.0, 0.0, 0.4), stroke_width=1,
            max_width_px=int(W * 0.75), align=PANGO_ALIGN_LEFT, padding=2,
        ),
        anchor=AnchorPoint.BOT_LEFT,
        fixed_position=(int(W * 0.02), int(H * 0.945)),
        margin_px=0,
    ))

    return blocks


# ═══════════════════════════════════════════════════════════════════════════════
# Template: Minimal
# ═══════════════════════════════════════════════════════════════════════════════

def make_minimal_blocks(
    W: int, H: int,
    offer: OfferData,
    brand: str = "airtel",
    zone_index: int = 0,
    font_family: str = "KongshoMJ",
) -> list:

    lang = offer.lang
    blocks = []

    segments = _build_headline_segments(offer, lang)
    if segments:
        headline_size = max(int(H * 0.07), 32)
        blocks.append(RichTextBlock(
            segments=segments,
            params=RenderParams(
                font_family=font_family, font_size=headline_size,
                bold=False, color=WHITE, stroke_color=RED,
                stroke_width=max(4, int(H * 0.006)),
                shadow_offset=(3, 3), shadow_blur=8,
                shadow_color=(0.0, 0.0, 0.0, 0.7),
                max_width_px=int(W * 0.50), align=PANGO_ALIGN_LEFT,
                line_spacing_px=6, padding=8,
            ),
            anchor=AnchorPoint.MID_LEFT,
            group_id="offer",
            margin_px=20,
            min_font_size=20,
        ))

    validity_text = offer.subline_bn if lang in ("bn", "mixed") else offer.subline_en
    if validity_text:
        # BIJOY CONVERSION for standalone TextBlock
        if font_family == "KongshoMJ" and needs_complex_shaping(validity_text):
            validity_text = BijoyConverter.convert(validity_text)
            
        subline_size = int(headline_size * 0.40)
        blocks.append(TextBlock(
            text=validity_text,
            params=RenderParams(
                font_family=font_family, font_size=subline_size,
                bold=False, color=WHITE, stroke_color=RED,
                stroke_width=max(2, int(H * 0.004)),
                shadow_offset=(1, 1), shadow_blur=3,
                shadow_color=(0.0, 0.0, 0.0, 0.4),
                max_width_px=int(W * 0.40), align=PANGO_ALIGN_LEFT, padding=4,
            ),
            anchor=AnchorPoint.MID_LEFT,
            group_id="offer",
            margin_px=20,
            min_font_size=30,
        ))

    # Offer Detail Badge
    details = []
    if offer.data_gb: details.append(offer.data_gb)
    if offer.price: details.append(offer.price)
    if offer.validity: details.append(offer.validity)
    
    if details:
        detail_text = " | ".join(details)
        # BIJOY CONVERSION for standalone TextBlock
        if font_family == "KongshoMJ" and needs_complex_shaping(detail_text):
            detail_text = BijoyConverter.convert(detail_text)
            
        badge_size = int(headline_size * 0.30)
        blocks.append(TextBlock(
            text=detail_text,
            params=RenderParams(
                font_family=font_family, font_size=badge_size,
                bold=True, color=WHITE,
                max_width_px=int(W * 0.45), align=PANGO_ALIGN_LEFT,
            ),
            anchor=AnchorPoint.MID_LEFT,
            group_id="offer",
            container="pill",
            container_kwargs={
                "fill_color": ROBI_RED if brand == "robi" else RED,
                "border_color": WHITE,
                "border_width": 1,
            },
            margin_px=15,
            min_font_size=18,
        ))

    return blocks


# ═══════════════════════════════════════════════════════════════════════════════
# Template: Story
# ═══════════════════════════════════════════════════════════════════════════════

def make_story_blocks(
    W: int, H: int,
    offer: OfferData,
    brand: str = "airtel",
    zone_index: int = 0,
    font_family: str = "KongshoMJ",
) -> list:

    lang = offer.lang
    blocks = []

    segments = _build_headline_segments(offer, lang)
    if segments:
        headline_size = max(int(W * 0.09), 34)
        blocks.append(RichTextBlock(
            segments=segments,
            params=RenderParams(
                font_family=font_family, font_size=headline_size,
                bold=False, color=WHITE, stroke_color=RED,
                stroke_width=max(5, int(W * 0.008)),
                shadow_offset=(3, 3), shadow_blur=8,
                shadow_color=(0.0, 0.0, 0.0, 0.7),
                max_width_px=int(W * 0.85), align=PANGO_ALIGN_CENTER, padding=10,
            ),
            anchor=AnchorPoint.BOT_CENTER,
            group_id="offer",
            margin_px=30,
            min_font_size=24,
        ))

    return blocks


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATE_REGISTRY: Dict[str, callable] = {
    "banner":   make_banner_blocks,
    "story":    make_story_blocks,
    "minimal":  make_minimal_blocks,
    "headline": make_headline_blocks,
}

TEMPLATE_META: Dict[str, AdTemplate] = {
    "banner": AdTemplate(
        name="banner", aspect_w=16, aspect_h=9,
        vignette=0.0, gradient_bar=False, gradient_side="bottom",
        gradient_coverage=0.30,
    ),
    "story": AdTemplate(
        name="story", aspect_w=9, aspect_h=16,
        vignette=0.0, gradient_bar=False, gradient_side="bottom",
        gradient_coverage=0.40,
    ),
    "minimal": AdTemplate(
        name="minimal", aspect_w=16, aspect_h=9,
        vignette=0.0, gradient_bar=False,
    ),
    "headline": AdTemplate(
        name="headline", aspect_w=16, aspect_h=9,
        vignette=0.0, gradient_bar=False, gradient_side="left",
        gradient_coverage=0.30,
    ),
}


def get_template_blocks(
    template_name: str,
    W: int, H: int,
    offer: OfferData,
    brand: str = "airtel",
    zone_index: int = 0,
    font_family: str = "KongshoMJ",
) -> list:

    fn = TEMPLATE_REGISTRY.get(template_name)
    if fn is None:
        raise ValueError(f"Unknown template '{template_name}'. Available: {list(TEMPLATE_REGISTRY.keys())}")
    return fn(W, H, offer, brand=brand, zone_index=zone_index, font_family=font_family)
