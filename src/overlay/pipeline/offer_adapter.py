"""
pipeline/offer_adapter.py
=========================
Task 3.1 — Connect to data sources and produce structured OfferData.

Supported sources:
  - CSV file (common for marketing ops)
  - JSON file / dict
  - REST API (GET endpoint returning JSON)
  - Direct dict construction

The adapter normalizes everything into the OfferData schema used by templates.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional
import urllib.request

from src.overlay.templates.style_templates import OfferData


# ─────────────────────────────────────────────────────────────────────────────
# CSV Adapter
# ─────────────────────────────────────────────────────────────────────────────

# Expected CSV columns (all optional except at least one headline):
# headline_bn, headline_en, subline_bn, subline_en,
# cta_bn, cta_en, price, data_gb, validity, brand, lang

CSV_COLUMN_DEFAULTS = {
    "headline_bn": "",
    "headline_en": "",
    "subline_bn": "",
    "subline_en": "",
    "cta_bn": "এখনই কিনুন",
    "cta_en": "Buy Now",
    "price": "",
    "data_gb": "",
    "validity": "",
    "brand": "airtel",
    "lang": "bn",
}


def load_from_csv(path: str | Path) -> List[OfferData]:
    """Load offers from a CSV file. Returns list of OfferData."""
    offers = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            merged = {**CSV_COLUMN_DEFAULTS, **{k: v for k, v in row.items() if v}}
            offers.append(OfferData(**{
                k: merged[k] for k in OfferData.__dataclass_fields__
            }))
    return offers


# ─────────────────────────────────────────────────────────────────────────────
# JSON Adapter
# ─────────────────────────────────────────────────────────────────────────────

def load_from_json(path_or_data: str | Path | dict | list) -> List[OfferData]:
    """Load offers from a JSON file or already-parsed dict/list."""
    if isinstance(path_or_data, (str, Path)):
        with open(path_or_data, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = path_or_data

    if isinstance(data, dict):
        data = [data]

    offers = []
    for item in data:
        merged = {**CSV_COLUMN_DEFAULTS, **item}
        offers.append(OfferData(**{
            k: str(merged.get(k, v))
            for k, v in CSV_COLUMN_DEFAULTS.items()
        }))
    return offers


# ─────────────────────────────────────────────────────────────────────────────
# REST API Adapter
# ─────────────────────────────────────────────────────────────────────────────

def load_from_api(url: str, timeout: int = 10) -> List[OfferData]:
    """
    Fetch offer data from a REST API endpoint.
    Expects JSON response: either a list of offer objects or a dict
    with an 'offers' / 'data' / 'results' key containing the list.
    """
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # Unwrap common envelope patterns
    if isinstance(data, dict):
        for key in ("offers", "data", "results", "items"):
            if key in data:
                data = data[key]
                break

    return load_from_json(data)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience builder
# ─────────────────────────────────────────────────────────────────────────────

def build_offer(
    price: str,
    data_gb: str,
    validity: str = "",
    brand: str = "airtel",
    lang: str = "bn",
    cta_bn: str = "এখনই কিনুন",
    extra_headline_bn: str = "",
    extra_headline_en: str = "",
) -> OfferData:
    """
    Build a standard telco data-offer from raw numbers.
    Auto-generates Bengali and English headline copy.
    """
    # Auto-generate headlines if not provided
    if not extra_headline_bn:
        validity_str = f" {validity}" if validity else ""
        headline_bn = f"মাত্র {price} টাকায় {data_gb} ইন্টারনেট!{validity_str}"
    else:
        headline_bn = extra_headline_bn

    if not extra_headline_en:
        headline_en = f"Only {price} for {data_gb} data!"
    else:
        headline_en = extra_headline_en

    subline_bn = f"ভ্যালিডিটি: {validity}" if validity else ""
    subline_en = f"Valid for: {validity}" if validity else ""

    return OfferData(
        headline_bn=headline_bn,
        headline_en=headline_en,
        subline_bn=subline_bn,
        subline_en=subline_en,
        cta_bn=cta_bn,
        cta_en="Buy Now",
        price=price,
        data_gb=data_gb,
        validity=validity,
        brand=brand,
        lang=lang,
    )
