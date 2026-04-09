"""Narrative generation for negotiation briefs (rule-based + LLM-enhanced)."""

import logging

from app.services.ollama import ollama_generate

logger = logging.getLogger(__name__)

BRIEF_SYSTEM_PROMPT = (
    "You are a senior procurement cost analyst writing a concise negotiation brief. "
    "Write in third person, use precise numbers from the data provided, and focus on "
    "actionable insights for the buyer. Keep your response to 3-5 sentences. "
    "Do not use markdown formatting, bullet points, or headers."
)


async def generate_enhanced_narrative(
    product_name: str,
    supplier_name: str | None,
    drivers: list[dict],
    gap: float | None,
    gap_pct: float | None,
    total_impact: float | None,
    currency: str,
    period_label: str,
    num_periods: int,
) -> str:
    """Attempt LLM-enhanced narrative; fall back to rule-based on any failure."""
    base = generate_narrative(
        product_name, supplier_name, drivers, gap, gap_pct,
        total_impact, currency, period_label, num_periods,
    )

    # Build structured prompt for the LLM
    driver_lines = []
    for d in sorted(drivers, key=lambda x: abs(x["contribution_to_gap"]), reverse=True)[:5]:
        idx = d["index_name"] or d["component_label"]
        driver_lines.append(
            f"- {d['component_label']}: linked to {idx}, "
            f"changed {d['index_change_pct']:+.1f}%, "
            f"contributing {currency} {d['contribution_to_gap']:+.3f}/unit ({d['direction']})"
        )

    gap_str = f"{currency} {gap:+.3f}/unit ({gap_pct:+.1f}%)" if gap is not None else "N/A"
    impact_str = f"{currency} {total_impact:,.0f}" if total_impact is not None else "N/A"

    prompt = (
        f"Product: {product_name}\n"
        f"Supplier: {supplier_name or 'Unknown'}\n"
        f"Period: {period_label} ({num_periods} quarters)\n"
        f"Currency: {currency}\n\n"
        f"Cost drivers (sorted by impact):\n" + "\n".join(driver_lines) + "\n\n"
        f"Price gap (actual vs should-cost): {gap_str}\n"
        f"Total financial impact over period: {impact_str}\n\n"
        f"Base analysis: {base}\n\n"
        f"Rewrite this analysis in a more insightful way. Highlight which cost driver "
        f"matters most and why, whether the buyer has negotiation leverage, and what "
        f"action they should consider. Be specific with the numbers provided."
    )

    try:
        enhanced = await ollama_generate(prompt, system=BRIEF_SYSTEM_PROMPT)
        return enhanced if enhanced else base
    except Exception:
        logger.warning("LLM narrative enhancement failed", exc_info=True)
        return base


def generate_narrative(
    product_name: str,
    supplier_name: str | None,
    drivers: list[dict],
    gap: float | None,
    gap_pct: float | None,
    total_impact: float | None,
    currency: str,
    period_label: str,
    num_periods: int,
) -> str:
    """
    Generate a rule-based negotiation narrative.

    drivers: list of dicts with keys:
        component_label, index_name, index_change_pct, contribution_to_gap, direction
    """
    parts = []

    # Opening
    supplier_str = f" from {supplier_name}" if supplier_name else ""
    parts.append(
        f"Analysis of {product_name}{supplier_str} over {period_label} "
        f"({num_periods} periods)."
    )

    # Top drivers
    top = sorted(drivers, key=lambda d: abs(d["contribution_to_gap"]), reverse=True)[:3]
    for d in top:
        direction = "rose" if d["direction"] == "up" else "fell" if d["direction"] == "down" else "remained flat"
        change = abs(d["index_change_pct"])

        idx_name = d["index_name"] or d["component_label"]
        contribution = abs(d["contribution_to_gap"])

        impact_word = "increasing" if d["direction"] == "up" else "reducing"

        parts.append(
            f"{d['component_label']} is linked to {idx_name}, which {direction} "
            f"{change:.1f}% over the period, {impact_word} should-cost by "
            f"{currency} {contribution:.3f}/unit."
        )

    # Verdict
    if gap is not None and total_impact is not None:
        if gap > 0.001:
            parts.append(
                f"Actual pricing has not reflected these cost movements, "
                f"generating an estimated {currency} {abs(total_impact):,.0f} "
                f"desqueeze (supplier margin expansion) over the period."
            )
        elif gap < -0.001:
            parts.append(
                f"The supplier has absorbed cost increases, resulting in an "
                f"estimated {currency} {abs(total_impact):,.0f} squeeze "
                f"(supplier margin compression) over the period."
            )
        else:
            parts.append(
                "Pricing has tracked should-cost within tolerance over the period."
            )
    elif gap is not None:
        if gap > 0.001:
            parts.append(
                f"Current actual price exceeds should-cost by "
                f"{currency} {abs(gap):.3f}/unit ({abs(gap_pct or 0):.1f}%), "
                f"suggesting potential for negotiation."
            )
        elif gap < -0.001:
            parts.append(
                f"Current actual price is below should-cost by "
                f"{currency} {abs(gap):.3f}/unit, indicating supplier margin compression."
            )

    return " ".join(parts)
