"""Shared Shopify GTIN helper.

The public storefront listing ``/products.json`` that our Shopify adapters use returns ``variant.barcode`` empty on
several shops (Deflorian, Kumitzberg, Goldblatt, Löwenanteil), while the public per-product endpoint
``/products/<handle>.json`` publishes the same variant **with** its barcode (verified 2026-10-25). This module fetches
that endpoint (polite gate, robots.txt respected via ``http.get``), keeps only GS1 check-digit-valid GTIN-8/12/13/14
and drops barcodes that the shop re-uses for several different products (placeholder pattern, e.g. Wagyuhof) — a
shared code never identifies a product, so it is never guessed onto one of them.
"""
from __future__ import annotations
from collections import Counter
from ..http import get


def valid_gtin(code) -> bool:
    s = str(code or "").strip()
    if not s.isdigit() or len(s) not in (8, 12, 13, 14) or set(s) == {"0"}:
        return False
    d = [int(c) for c in s]
    body = d[:-1][::-1]
    return (10 - sum(v * (3 if i % 2 == 0 else 1) for i, v in enumerate(body)) % 10) % 10 == d[-1]


def gtin(variant: dict | None) -> str | None:
    b = str((variant or {}).get("barcode") or "").strip()
    return b if valid_gtin(b) else None


def product_json_barcodes(base: str, handle: str) -> dict[str, str]:
    """``{variant_id: barcode}`` from ``<base>/products/<handle>.json``; {} on any error (never raises)."""
    try:
        p = get(f"{base.rstrip('/')}/products/{handle}.json", timeout=30).get("product") or {}
    except Exception:
        return {}
    return {str(v.get("id")): str(v.get("barcode")).strip() for v in p.get("variants") or [] if v.get("barcode")}


def merge_barcodes(sp: dict, barcodes: dict[str, str]) -> dict:
    """Fill empty ``variant.barcode`` of a products.json entry in place from ``barcodes`` (by variant id)."""
    for v in sp.get("variants") or []:
        if not v.get("barcode") and barcodes.get(str(v.get("id"))):
            v["barcode"] = barcodes[str(v.get("id"))]
    return sp


def enrich(base: str, sp: dict) -> dict:
    return merge_barcodes(sp, product_json_barcodes(base, sp.get("handle") or ""))


def drop_shared(products: list) -> list:
    """Null ``ean`` on Products whose GTIN appears on more than one differently named product."""
    names: dict[str, set] = {}
    for p in products:
        if p.ean:
            names.setdefault(p.ean, set()).add(p.name)
    for p in products:
        if p.ean and len(names[p.ean]) > 1:
            p.extra["gtin_note"] = f"barcode {p.ean} shared by {len(names[p.ean])} products → not used"
            p.ean = None
    return products
