import re
from dataclasses import dataclass, field

from food_order_bot.models import SwiggySurface

MIN_PRICE_WORDS = {
    "cheap",
    "cheapest",
    "budget",
    "minimum",
    "min",
    "minm",
    "low",
    "lowest",
    "rate",
    "sasta",
    "sasti",
    "kam",
}

FILLER_WORDS = {
    "and",
    "aur",
    "or",
    "kii",
    "ki",
    "ka",
    "ke",
    "the",
    "some",
    "an",
    "dsome",
    "please",
    "pls",
    "mujhe",
    "chahiye",
    "order",
    "near",
    "nearby",
    "rate",
    "price",
}

HINGLISH_NORMALIZATIONS = {
    "aalo": "aloo",
    "alu": "aloo",
    "sabji": "sabzi",
    "chappati": "chapati",
    "chapatti": "chapati",
    "roti": "chapati",
}


@dataclass(frozen=True)
class FoodRequest:
    original_text: str
    surface: SwiggySurface
    query: str
    budget_preference: str | None = None
    quantities: dict[str, int] = field(default_factory=dict)

    @property
    def is_order_like(self) -> bool:
        return bool(self.query)


class FoodRequestAnalyzer:
    """Small deterministic parser that agents can use before model reasoning."""

    def analyze(self, text: str) -> FoodRequest:
        normalized = _normalize(text)
        surface = _surface_for(normalized)
        quantities = _extract_quantities(normalized)
        budget = (
            "minimum_price"
            if any(word in normalized.split() for word in MIN_PRICE_WORDS)
            else None
        )
        query = _clean_query(normalized)
        return FoodRequest(
            original_text=text,
            surface=surface,
            query=query,
            budget_preference=budget,
            quantities=quantities,
        )


def _normalize(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    words = [HINGLISH_NORMALIZATIONS.get(word, word) for word in lowered.split()]
    return " ".join(words)


def _surface_for(text: str) -> SwiggySurface:
    if any(word in text for word in ("instamart", "grocery", "groceries")):
        return SwiggySurface.INSTAMART
    if any(word in text for word in ("dineout", "table", "reservation", "booking")):
        return SwiggySurface.DINEOUT
    return SwiggySurface.FOOD


def _extract_quantities(text: str) -> dict[str, int]:
    quantities: dict[str, int] = {}
    for match in re.finditer(r"\b(\d+)\s+([a-z][a-z0-9]*)", text):
        count = int(match.group(1))
        item = HINGLISH_NORMALIZATIONS.get(match.group(2), match.group(2))
        quantities[item] = count
    return quantities


def _clean_query(text: str) -> str:
    words = []
    for word in text.split():
        if word.isdigit() or word in FILLER_WORDS or word in MIN_PRICE_WORDS:
            continue
        words.append(word)
    compacted = " ".join(words)
    compacted = re.sub(r"\s+", " ", compacted).strip()
    return compacted
