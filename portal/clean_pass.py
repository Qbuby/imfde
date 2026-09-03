# -*- coding: utf-8 -*-
"""Case-library clean rules for build_portal_db.py (2026-08-29 pass).

Does not rewrite shards. measured_outcome is never deleted.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
AI_ROOT = HERE.parent
VENDOR_ALIASES = AI_ROOT / "fde_corpus" / "vendor_aliases.json"
KPI_FLAGS = HERE / "kpi_flags.json"

GLEAN_TEMPLATE_NOTE = "1.5+ hours saved"
KPI_SCOPE_VALUES = ("narrative", "hero_only", "goal", "projected", "system_scale_not_kpi")
CLEAN_FLAG_VALUES = KPI_SCOPE_VALUES + ("leftover_template", "hub_kpi_not_on_page")


def norm_url(u: str) -> str:
    s = (u or "").strip()
    if not s:
        return ""
    return s.rstrip("/").lower()


def load_vendor_alias_doc() -> dict:
    if not VENDOR_ALIASES.is_file():
        return {"aliases": {}, "canonical_names": {}}
    return json.loads(VENDOR_ALIASES.read_text(encoding="utf-8"))


def load_kpi_flag_index() -> dict[str, dict]:
    if not KPI_FLAGS.is_file():
        return {}
    doc = json.loads(KPI_FLAGS.read_text(encoding="utf-8"))
    out = {}
    for row in doc.get("rows") or []:
        out[norm_url(row.get("url") or "")] = row
    return out


def apply_vendor_aliases(explicit_aliases: dict[str, str], extra_names: dict[str, str]) -> dict[str, str]:
    """Mutate EXPLICIT_ALIASES / EXTRA_NAMES. Return product-by-norm-key."""
    doc = load_vendor_alias_doc()
    products: dict[str, str] = {}
    for key, spec in (doc.get("aliases") or {}).items():
        if not key:
            continue
        nk = re.sub(r"\s+", " ", str(key).strip().lower())
        if isinstance(spec, str):
            slug, product, name = spec, None, None
        else:
            slug = spec.get("slug")
            product = spec.get("product")
            name = spec.get("name")
        if not slug:
            continue
        explicit_aliases.setdefault(nk, slug)
        if name:
            extra_names.setdefault(slug, name)
        if product:
            products[nk] = product
    for slug, name in (doc.get("canonical_names") or {}).items():
        extra_names.setdefault(slug, name)
    return products


def product_for_company(raw: str, products: dict[str, str]) -> str | None:
    nk = re.sub(r"\s+", " ", (raw or "").strip().lower())
    if nk in products:
        return products[nk]
    return None


def flags_for_case(url: str, evidence_note: str, kpi_index: dict[str, dict]) -> tuple[str | None, list[dict]]:
    """Return (kpi_scope, flags[{flag,reason}])."""
    flags: list[dict] = []
    seen = set()
    row = kpi_index.get(norm_url(url))
    scope = None
    if row:
        scope = row.get("kpi_scope")
        for f in row.get("flags") or []:
            flag = f.get("flag")
            if flag and flag not in seen:
                flags.append({"flag": flag, "reason": f.get("reason") or ""})
                seen.add(flag)
    note = evidence_note or ""
    if GLEAN_TEMPLATE_NOTE in note and "leftover_template" not in seen:
        flags.append({
            "flag": "leftover_template",
            "reason": "Glean hero chip '1.5+ hours saved / search time saved per employee, weekly' repeats on many stories and is not treated as a customer-specific KPI (mine_loop_20260829_glean).",
        })
        seen.add("leftover_template")
    if scope not in KPI_SCOPE_VALUES:
        scope = None
    return scope, flags


def default_kpi_scope(measured_outcome: str, existing: str | None) -> str | None:
    if existing:
        return existing
    if (measured_outcome or "").strip():
        return "narrative"
    return None


def customer_from_same_row(customer: str, source_title: str) -> tuple[str, bool]:
    """Fill empty customer only when the title already carries a clear same-row name.

    Conservative: never invent. Current library has no safe title-only fills
    for case_study rows (the one empty case_study title is an a16z essay).
    """
    cust = re.sub(r"\s+", " ", (customer or "").strip())
    if cust:
        return cust, False
    return "", False
