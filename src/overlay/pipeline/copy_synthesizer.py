"""
pipeline/copy_synthesizer.py
============================
Task 3.2 — Generate ad copy from structured offer data.

Implements:
  - Rule-based Bengali & English copy templates (works offline, fast)
  - LLM integration stub (Anthropic / OpenAI / local) for catchy copy
  - Language selector: "bn" | "en" | "mixed"

The rule-based fallback always runs; LLM is optional and additive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from src.overlay.templates.style_templates import OfferData


# ─────────────────────────────────────────────────────────────────────────────
# Bengali numeral converter
# ─────────────────────────────────────────────────────────────────────────────

_EN_TO_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
_BN_TO_EN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def to_bengali_numerals(text: str) -> str:
    """Convert ASCII digits in text to Bengali digits."""
    return text.translate(_EN_TO_BN_DIGITS)


def strip_bengali_numerals(text: str) -> str:
    """Convert Bengali digits back to ASCII."""
    return text.translate(_BN_TO_EN_DIGITS)


# ─────────────────────────────────────────────────────────────────────────────
# Rule-based copy templates
# ─────────────────────────────────────────────────────────────────────────────

# ── Banglish templates (BN script + English keywords mixed) ──────────────
# Short, punchy. Bengali numerals for BN, English for EN.
_BN_HEADLINE_TEMPLATES = [
    "{data} Internet\nমাত্র {price} টাকায়!",
    "মাত্র {price} টাকায়\nপাও {data}!",
    "Best Deal!\n{data} মাত্র {price} Tk!",
    "Super Offer!\n{data} @ {price} টাকা",
    "{data} Internet\nপাও মাত্র {price} তে!",
]

_BN_SUBLINE_TEMPLATES = [
    "মেয়াদ {validity} দিন",
    "{validity} দিন চলবে!",
]

_BN_CTA_OPTIONS = [
    "Grab Now!",
    "অফার নাও!",
    "Get It!",
    "কিনে ফেলো!",
]

# Smart disclaimer (tiny text, bottom placement like real agency work)
_DISCLAIMER_TEMPLATES = [
    '*"এয়ারটেল" রবি আক্সিয়াটা লিমিটেড-এর একটি ব্র্যান্ড',
    "*শর্ত প্রযোজ্য | যেকোনো নেটওয়ার্কে ব্যবহারযোগ্য",
]

# English templates
_EN_HEADLINE_TEMPLATES = [
    "Get {data}\nat just Tk{price}!",
    "{data} Internet\nOnly Tk{price}!",
    "Best Deal!\n{data} @ Tk{price}",
    "Super Offer:\n{data} for Tk{price}!",
]

_EN_SUBLINE_TEMPLATES = [
    "Valid for {validity} days | 4G",
    "{validity}-day validity",
    "Offer valid {validity} days",
]

_EN_CTA_OPTIONS = [
    "Grab Now!",
    "Get It!",
    "Buy Now",
    "Activate!",
]

_MIXED_SUBLINE = "মেয়াদ: {validity} দিন"


# ─────────────────────────────────────────────────────────────────────────────
# Synthesizer
# ─────────────────────────────────────────────────────────────────────────────

class CopySynthesizer:
    """
    Generates ad copy for a given OfferData using rule-based templates.

    Optionally upgrades copy with an LLM call if api_key is provided.

    Usage:
        synth = CopySynthesizer()
        offer = synth.generate(price="৳৪৯", data_gb="৩ জিবি",
                               validity="৩০ দিন", brand="airtel", lang="bn")
    """

    def __init__(
        self,
        llm_api_key: Optional[str] = None,
        llm_provider: str = "anthropic",  # "anthropic" | "openai"
        template_variant: int = 0,        # 0-based index into template lists
    ):
        self._llm_key = llm_api_key
        self._llm_provider = llm_provider
        self._variant = template_variant

    # ── Public API ─────────────────────────────────────────────────────────

    def generate(
        self,
        price: str,
        data_gb: str,
        validity: str = "30",
        brand: str = "airtel",
        lang: str = "bn",
        cta_index: int = 0,
    ) -> OfferData:
        """
        Generate OfferData with Banglish copy.

        For BN: Bengali numerals + Bengali script + some English words
        For EN: Clean English with Tk prefix
        """
        # Clean numbers (strip symbols)
        price_raw = price.replace("৳", "").replace("Tk", "").strip()
        data_raw = data_gb.strip()
        validity_raw = validity.replace("দিন", "").replace("days", "").strip()

        # Bengali numerals
        price_bn = to_bengali_numerals(price_raw)
        data_bn_num = to_bengali_numerals(data_raw.replace("GB", "").replace("gb", "").strip())
        data_bn = f"{data_bn_num} জিবি" if data_raw.upper().endswith("GB") else to_bengali_numerals(data_raw)
        validity_bn = to_bengali_numerals(validity_raw)

        # English clean
        price_en = strip_bengali_numerals(price_raw)
        data_en = strip_bengali_numerals(data_raw)
        validity_en = strip_bengali_numerals(validity_raw)

        vi = self._variant % len(_BN_HEADLINE_TEMPLATES)

        # BN: Banglish with Bengali numerals
        headline_bn = _BN_HEADLINE_TEMPLATES[vi].format(
            price=price_bn, data=data_bn, validity=validity_bn
        )
        subline_bn = _BN_SUBLINE_TEMPLATES[vi % len(_BN_SUBLINE_TEMPLATES)].format(
            price=price_bn, data=data_bn, validity=validity_bn
        ) if validity_raw else ""

        # EN: Clean English
        headline_en = _EN_HEADLINE_TEMPLATES[vi % len(_EN_HEADLINE_TEMPLATES)].format(
            price=price_en, data=data_en, validity=validity_en
        )
        subline_en = _EN_SUBLINE_TEMPLATES[vi % len(_EN_SUBLINE_TEMPLATES)].format(
            price=price_en, data=data_en, validity=validity_en
        ) if validity_raw else ""

        cta_bn = _BN_CTA_OPTIONS[cta_index % len(_BN_CTA_OPTIONS)]
        cta_en = _EN_CTA_OPTIONS[cta_index % len(_EN_CTA_OPTIONS)]

        disclaimer = _DISCLAIMER_TEMPLATES[vi % len(_DISCLAIMER_TEMPLATES)]

        offer = OfferData(
            headline_bn=headline_bn,
            headline_en=headline_en,
            subline_bn=subline_bn,
            subline_en=subline_en,
            cta_bn=cta_bn,
            cta_en=cta_en,
            price=price_bn if lang == "bn" else price_en,
            data_gb=data_bn if lang == "bn" else data_en,
            validity=validity_bn if lang == "bn" else validity_en,
            brand=brand,
            lang=lang,
        )

        if self._llm_key:
            try:
                offer = self._enhance_with_llm(offer)
            except Exception as e:
                print(f"[CopySynthesizer] LLM enhancement failed: {e}")

        return offer

    def enhance_offer(self, offer: OfferData) -> OfferData:
        """
        Fill missing copy fields in an existing OfferData using rule-based templates.
        Useful when OfferData comes from CSV with some blanks.
        """
        vi = self._variant
        if not offer.headline_bn and offer.price:
            offer.headline_bn = _BN_HEADLINE_TEMPLATES[vi % len(_BN_HEADLINE_TEMPLATES)].format(
                price=offer.price, data=offer.data_gb, validity=offer.validity
            )
        if not offer.headline_en and offer.price:
            offer.headline_en = _EN_HEADLINE_TEMPLATES[vi % len(_EN_HEADLINE_TEMPLATES)].format(
                price=strip_bengali_numerals(offer.price),
                data=offer.data_gb,
                validity=strip_bengali_numerals(offer.validity),
            )
        if not offer.cta_bn:
            offer.cta_bn = _BN_CTA_OPTIONS[0]
        if not offer.cta_en:
            offer.cta_en = _EN_CTA_OPTIONS[0]
        return offer

    # ── LLM stub ───────────────────────────────────────────────────────────

    def _enhance_with_llm(self, offer: OfferData) -> OfferData:
        """
        (Stub) Call LLM to generate catchy copy.
        Replace the rule-based headlines with LLM-generated ones.

        To activate: pass llm_api_key to CopySynthesizer.
        Supports Anthropic (claude-3-haiku) or OpenAI (gpt-4o-mini).
        """
        prompt = f"""You are a creative copywriter for {offer.brand.title()} Bangladesh.
Write a short, punchy Bengali headline (max 12 words) for this telecom offer:
- Price: {offer.price} BDT
- Data: {offer.data_gb}
- Validity: {offer.validity}

Rules:
- Use Bengali script only
- Include the price and data amount
- Sound exciting and urgent
- Do NOT use emojis

Respond with just the headline, nothing else."""

        if self._llm_provider == "anthropic":
            return self._call_anthropic(offer, prompt)
        elif self._llm_provider == "openai":
            return self._call_openai(offer, prompt)
        return offer

    def _call_anthropic(self, offer: OfferData, prompt: str) -> OfferData:
        """Call Anthropic API for LLM copy."""
        import urllib.request, json
        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._llm_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        llm_headline = data["content"][0]["text"].strip()
        offer.headline_bn = llm_headline
        return offer

    def _call_openai(self, offer: OfferData, prompt: str) -> OfferData:
        """Call OpenAI API for LLM copy."""
        import urllib.request, json
        body = json.dumps({
            "model": "gpt-4o-mini",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._llm_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        llm_headline = data["choices"][0]["message"]["content"].strip()
        offer.headline_bn = llm_headline
        return offer
