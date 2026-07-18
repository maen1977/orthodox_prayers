#!/usr/bin/env python3
"""Single source of truth for top-level signed daily publication readiness.

The project supports two equivalent publication envelopes:
1. the older fully materialized VERIFIED_OFFICIAL_SOURCES envelope; and
2. the newer fail-closed native-language envelope, where daily_availability may
   be PARTIAL_VERIFIED while all release-required Scripture is exact and verified.

The second envelope is intentionally completed by validate_release_readiness.py;
this module only validates the top-level publication policy consistently.
"""
from __future__ import annotations
from typing import Any

LEGACY_STATUS = "VERIFIED_OFFICIAL_SOURCES"
NATIVE_PUBLICATION_STATUS = "AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED"
NATIVE_CONTRACT = "canonical/source_native_contract.json"
ALLOWED_AVAILABILITY = {"FULL", "PARTIAL_VERIFIED"}


def top_level_errors(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    integrity = data.get("integrity") or {}
    publication = data.get("publication") or {}

    if integrity.get("status") == LEGACY_STATUS:
        if integrity.get("ai_scripture_translation_used") is not False:
            errors.append("legacy integrity must disable AI Scripture translation")
        if integrity.get("ai_liturgical_translation_used") is not False:
            errors.append("legacy integrity must disable AI liturgical translation")
        return errors

    if publication.get("status") != NATIVE_PUBLICATION_STATUS:
        errors.append("publication status is not the fail-closed native-language policy")
    if publication.get("fail_closed") is not True:
        errors.append("publication is not fail-closed")
    if publication.get("same_language_fallback_only") is not True:
        errors.append("publication permits cross-language fallback")
    if publication.get("religious_text_contract") != NATIVE_CONTRACT:
        errors.append("publication native-text contract is missing or invalid")
    if publication.get("daily_availability") not in ALLOWED_AVAILABILITY:
        errors.append("daily availability is neither FULL nor PARTIAL_VERIFIED")
    if publication.get("human_review_required") is not False:
        errors.append("automatic publication unexpectedly requires a daily human reviewer")
    if data.get("native_text_contract") != NATIVE_CONTRACT:
        errors.append("top-level native-text contract is missing or invalid")
    if integrity.get("native_text_contract") != NATIVE_CONTRACT:
        errors.append("integrity native-text contract is missing or invalid")
    if data.get("machine_translation_used") is not False:
        errors.append("machine translation must be explicitly disabled")
    if data.get("automatic_diacritization_used") is not False:
        errors.append("automatic diacritization must be explicitly disabled")
    return errors


def is_top_level_ready(data: dict[str, Any]) -> bool:
    return not top_level_errors(data)
