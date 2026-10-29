"""Optional AI-assisted product enrichment service using existing Groq/AI provider."""

import json
import re
from typing import List, Optional

import structlog

from app.ai.base import AIMessage
from app.ai.factory import get_ai_provider
from app.catalogue.models import AIEnrichmentResponse, AIEnrichmentSuggestion, ProductRecord
from app.core.config import settings

logger = structlog.get_logger(__name__)


async def enrich_products_ai(
    products: List[ProductRecord],
    enrichment_types: Optional[List[str]] = None,
) -> AIEnrichmentResponse:
    """Generate advisory product enhancements (description polish, category, SEO, tags).

    Strictly grounded in provided product attributes with zero fabrication of SKUs, prices, or inventory.
    """
    types = enrichment_types or ["description", "category", "seo", "tags"]
    # Limit batch to first 25 products per call to avoid token limit or timeout
    batch = products[:25]

    # Prepare compact fact-grounded context
    compact_items = []
    for p in batch:
        item = {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "brand": p.brand or "",
            "category": p.category or "",
            "raw_description": p.description or p.short_description or "",
            "price": p.price,
            "color": p.color or "",
            "material": p.material or "",
        }
        compact_items.append(item)

    system_instruction = (
        "You are Rivu AI's senior e-commerce merchandising intelligence analyst.\n"
        "Your task is to enrich and polish product catalogue records for online retail and ERP systems.\n"
        "CRITICAL RULES:\n"
        "1. NEVER invent, hallucinate or change prices, SKUs, barcodes, or technical dimensions.\n"
        "2. Polish descriptions into crisp, professional, grammatically impeccable customer-facing copy.\n"
        "3. Suggest standard e-commerce retail categories based on product titles.\n"
        "4. Provide SEO titles strictly under 60 characters and SEO meta descriptions strictly under 155 characters.\n"
        "5. Output valid JSON ONLY matching the requested structure.\n"
    )

    user_prompt = f"""Enrich the following product items based on requested enrichment types: {types}.

Return ONLY a valid JSON object with a single key "suggestions" containing an array of objects:
[
  {{
    "product_id": "string",
    "suggested_description": "polished text (or null)",
    "suggested_category": "standard category (or null)",
    "suggested_seo_title": "title under 60 chars (or null)",
    "suggested_seo_description": "meta description under 155 chars (or null)",
    "suggested_tags": ["tag1", "tag2", "tag3"],
    "reasoning": "1 brief sentence explaining the enrichment"
  }}
]

PRODUCT ITEMS:
{json.dumps(compact_items, indent=2)}
"""

    provider_name = settings.DEFAULT_AI_PROVIDER
    model_name = settings.GROQ_MODEL

    try:
        provider = get_ai_provider()
        response = await provider.complete_json(
            [
                AIMessage("system", system_instruction),
                AIMessage("user", user_prompt),
            ],
            temperature=0.2,
            max_tokens=4000,
        )

        try:
            parsed = json.loads(response.content)
            raw_suggestions = parsed.get("suggestions", [])
        except Exception:
            raw_suggestions = []

        suggestions: List[AIEnrichmentSuggestion] = []
        for raw in raw_suggestions:
            if isinstance(raw, dict) and "product_id" in raw:
                suggestions.append(AIEnrichmentSuggestion(
                    product_id=str(raw["product_id"]),
                    suggested_description=raw.get("suggested_description"),
                    suggested_category=raw.get("suggested_category"),
                    suggested_seo_title=raw.get("suggested_seo_title"),
                    suggested_seo_description=raw.get("suggested_seo_description"),
                    suggested_tags=raw.get("suggested_tags") if isinstance(raw.get("suggested_tags"), list) else None,
                    reasoning=raw.get("reasoning"),
                ))

        # Fill any missing products with rule-based fallback suggestions
        matched_ids = {s.product_id for s in suggestions}
        for p in batch:
            if p.id not in matched_ids:
                suggestions.append(_generate_rule_based_fallback(p, types))

        return AIEnrichmentResponse(
            suggestions=suggestions,
            model_used=response.model or model_name,
            provider=response.provider or provider_name,
        )

    except Exception as exc:
        logger.warning("ai_enrichment_provider_unavailable", error=str(exc))
        # Deterministic rule-based fallback if AI credentials are not configured or call times out
        fallback_suggestions = [_generate_rule_based_fallback(p, types) for p in batch]
        return AIEnrichmentResponse(
            suggestions=fallback_suggestions,
            model_used="deterministic-rule-engine",
            provider="local-fallback",
        )


def _generate_rule_based_fallback(p: ProductRecord, types: List[str]) -> AIEnrichmentSuggestion:
    """Generate high-quality rule-based fallback suggestions when LLM is unavailable."""
    title = p.name.strip() if p.name else f"Product {p.sku}"
    brand_prefix = f"{p.brand} " if p.brand else ""

    # Never invent product properties; use only facts already present in the record.
    desc = p.description or p.short_description
    seo_title = f"{brand_prefix}{title}"[:58]
    seo_source = p.short_description or p.description or title
    seo_desc = seo_source[:150] if seo_source else None

    # Tag extraction from title
    words = [w.lower() for w in re.split(r"[^a-zA-Z0-9]+", title) if len(w) > 3]
    tags = list(dict.fromkeys(words))[:5]
    if p.brand:
        tags.insert(0, p.brand.lower())

    return AIEnrichmentSuggestion(
        product_id=p.id,
        suggested_description=desc if "description" in types else None,
        suggested_category=p.category if "category" in types else None,
        suggested_seo_title=seo_title if "seo" in types else None,
        suggested_seo_description=seo_desc if "seo" in types else None,
        suggested_tags=tags if "tags" in types else None,
        reasoning="Rule-based semantic standardization applied.",
    )
