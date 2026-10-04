from __future__ import annotations


def build_explanation(
    crop: str,
    weather: dict,
    market: dict,
    profit: dict,
    risk: dict,
    evidence: list[dict],
) -> str:
    sentiment = market.get("sentiment")
    sentiment_line = (
        "No stored or live sentiment signal was available, so the market note uses prices only."
        if sentiment is None
        else (
            f"The sentiment index in this result is {sentiment:.2f} "
            f"({market.get('sentiment_status')}, as of {market.get('sentiment_as_of')}). "
            "Sentiment is a market signal and is not converted directly into profit."
        )
    )
    sources = []
    for item in evidence:
        title = item.get("title") or "Untitled document"
        section = item.get("section")
        label = f"{title} / {section}" if section else title
        if label not in sources:
            sources.append(label)
    source_block = "\n".join(f"- {name}" for name in sources) if sources else "- No matching agricultural document was retrieved."
    return "\n".join(
        [
            f"Why {crop} received this result",
            "",
            "1. Temperature",
            (
                f"Temperature suitability is {weather['temperature_score']:.0%} of the documented range "
                "across the modeled growing period. Days after the forecast window use monthly climate normals."
            ),
            "",
            "2. Rainfall",
            (
                f"Rainfall suitability is {weather['rainfall_score']:.0%}. "
                f"Extreme-weather exposure covers {weather['extreme_weather_risk']:.0%} of the modeled days."
            ),
            "",
            "3. Market",
            (
                f"The price band used here is {market['price_range']['min']:.2f} to "
                f"{market['price_range']['max']:.2f} {market.get('unit', 'PHP/kg')}. {sentiment_line}"
            ),
            "",
            "4. Production",
            (
                f"The yield band is {profit['yield']['min']:.0f} to {profit['yield']['max']:.0f} kg "
                f"for this farm size. Expected profit is {profit['profit']['expected']} PHP, "
                f"with a conservative figure of {profit['profit']['conservative']} PHP and an optimistic figure of "
                f"{profit['profit']['optimistic']} PHP."
            ),
            "",
            "5. Risk",
            (
                f"Overall risk is {risk['overall']}/100 ({risk['overall_label']}). "
                f"Weather {risk['weather']}, market {risk['market']}, production {risk['production']}, "
                f"data {risk['data']}."
            ),
            "",
            "These statements repeat the calculated figures and name retrieved documents. They are scenarios, not a guarantee.",
            "",
            "Sources:",
            source_block,
        ]
    )
