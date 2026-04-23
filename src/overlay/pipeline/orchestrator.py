"""
orchestrator.py
===============
Full pipeline orchestrator. One image + one offer = one ad asset.

V3: Random font per banner, rich text support, no containers.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PIL import Image

from src.overlay.renderer.font_engine import (
    FontManager, FontRegistry, UnifiedRenderer, pick_random_font,
)
from src.overlay.renderer.layout import LayoutEngine
from src.overlay.renderer.effects import add_vignette, BrandPalette, analyze_luminance
from src.overlay.renderer.containers import gradient_overlay
from src.overlay.layout.dead_space import DeadSpaceFinder
from src.overlay.branding.logo_handler import LogoHandler
from src.overlay.templates.style_templates import get_template_blocks, TEMPLATE_META, OfferData
from src.overlay.pipeline.offer_adapter import build_offer, load_from_csv
from src.overlay.pipeline.copy_synthesizer import CopySynthesizer
from src.generator.intelligence.highlight_analyzer import HighlightAnalyzer
from src.generator.bedrock.bedrock_client import BedrockClient



_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FONT_DIR = _PROJECT_ROOT / "assets" / "fonts"
NEW_FONT_DIR = FONT_DIR / "new"


class AdOrchestrator:
    def __init__(
        self,
        font_dir: Optional[str | Path] = None,
        latin_font: Optional[str] = None,
        output_dir: str | Path = "output",
    ):
        self._font_dir = Path(font_dir or FONT_DIR)
        self._output = Path(output_dir)
        self._output.mkdir(parents=True, exist_ok=True)

        # Setup font manager (downloads Google Fonts on first run)
        self._font_manager = FontManager(
            custom_font_dir=self._font_dir
        )
        self._font_manager.ensure_google_fonts()

        # Register NEW artistic fonts
        if NEW_FONT_DIR.exists():
            for ext in ("*.ttf", "*.otf"):
                for fp in NEW_FONT_DIR.glob(ext):
                    self._font_manager._font_paths[fp.stem] = fp
            print(f"  ✓ Registered {len(list(NEW_FONT_DIR.glob('*.ttf')))} new fonts")

        # Resolve Latin font path
        latin_font_path = latin_font
        if latin_font_path is None:
            tondo = self._font_manager.get_path("Tondo_Std_Rg")
            if tondo is None:
                tondo = self._font_manager.get_path("Tondo_Std")
            latin_font_path = str(tondo) if tondo else None

        # Core components
        self._renderer = UnifiedRenderer(
            font_manager=self._font_manager,
            latin_font_path=latin_font_path,
        )
        self._layout = LayoutEngine(self._renderer)
        self._finder = DeadSpaceFinder()
        self._logo = LogoHandler()
        
        # LLM Highlight Analyzer
        try:
            self._bedrock = BedrockClient()
            self._highlighter = HighlightAnalyzer(self._bedrock)
        except Exception as e:
            print(f"  ⚠️ Warning: Could not initialize LLM Highlighter: {e}")
            self._highlighter = None


    async def render_single(
        self,
        image_path: str | Path,
        offer: OfferData,
        template: str = "banner",
        logo_path: Optional[str | Path] = None,
        output_name: Optional[str] = None,
        font_family: Optional[str] = None,
    ) -> Path:

        """
        Render one ad. Returns output path.

        font_family: if None, picks a random font from the new fonts dir.
        """
        base = Image.open(image_path).convert("RGB")
        W, H = base.size
        meta = TEMPLATE_META.get(template)

        # Lock to specific requested font: KongshoMJ (Bijoy)
        if font_family is None:
            font_family = "KongshoMJ"
            print(f"  🎨 Defaulting to professional Bijoy font: {font_family}")
        else:
            print(f"  🎨 Using font: {font_family}")


        # 1. Apply background effects
        result = base.copy()
        if meta and meta.vignette > 0:
            result = add_vignette(result, strength=meta.vignette)
        if meta and meta.gradient_bar:
            coverage = getattr(meta, 'gradient_coverage', 0.4)
            result = gradient_overlay(
                result,
                side=meta.gradient_side,
                coverage=coverage,
                color=(0, 0, 0, 180),
            )

        # 1b. UNIFIED LLM Highlighting (The "Poppy Designer")
        if self._highlighter and not offer.headline_segments:
            self._highlighter.clear_cache()
            
            try:
                # Gather all ad components for unified context
                offer_payload = {
                    "headline": offer.headline_bn or offer.headline_en,
                    "subline": offer.subline_bn or offer.subline_en,
                    "details": [offer.data_gb, offer.price, offer.validity],
                    "brand": offer.brand
                }
                
                # Call the new unified analyzer with await (since render_single is now async)
                styling_map = await self._highlighter.analyze_full_ad(offer_payload)
                
                if styling_map:
                    def _unwrap(val):
                        """LLM sometimes returns {"segments": [...]} instead of [...]."""
                        if isinstance(val, dict) and "segments" in val:
                            return val["segments"]
                        if isinstance(val, list):
                            return val
                        return []

                    offer.headline_segments = _unwrap(styling_map.get("headline", []))
                    offer.subline_segments = _unwrap(styling_map.get("subline", []))
                    offer.detail_segments = _unwrap(styling_map.get("offer_badge", []))
                    print(f"  ✨ Poppy Styling Applied to all components")


            except Exception as e:
                print(f"  ⚠️ Unified highlight analysis failed: {e}")



        # 2. Find safe zones using DeadSpaceFinder
        zones = self._finder.find(base, top_k=8)

        # 3. Get template text blocks (with random font)
        blocks = get_template_blocks(
            template, W, H, offer,
            brand=offer.brand, zone_index=0,
            font_family=font_family,
        )

        # 4. Apply text layout (passing the detected zones!)
        result = self._layout.apply(
            result.convert("RGBA"), blocks, safe_zones=zones
        )

        # 4. Logo
        if logo_path:
            result = self._logo.paste(result, logo_path, brand=offer.brand)

        # 5. Save
        stem = Path(image_path).stem
        name = output_name or f"{stem}.png"
        out_path = self._output / name
        result.convert("RGB").save(str(out_path), quality=95)
        print(f"  ✓ Saved: {out_path}")
        return out_path

    async def render_batch(
        self,
        image_paths: list[str | Path],
        offers: list[OfferData],
        templates: list[str] = ("banner",),
        logo_path: Optional[str | Path] = None,
    ) -> list[Path]:
        """Cross-product: each image × each offer × each template."""
        results = []
        total = len(image_paths) * len(offers) * len(templates)
        print(f"🚀 Batch rendering {total} variations...")
        
        for img in image_paths:
            for offer in offers:
                for tmpl in templates:
                    res = await self.render_single(img, offer, template=tmpl, logo_path=logo_path)
                    results.append(res)
        return results