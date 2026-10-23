"""How many Picnic packs a shopping item needs.

Recipes are written in packs: "2 minced meat" means two packs, and no quantity
means one. Which pack (500 g or 1 kg) is part of the item's mapping. A
quantity in a measuring unit ("500 g") is not a pack count, so that is one
pack too rather than five hundred.
"""

import math

_MEASURES = {
    "g", "gr", "gram", "kg", "kilo", "mg",
    "ml", "cl", "dl", "l", "liter", "litre",
    "tl", "el", "tsp", "tbsp", "cup", "cups",
}


def pack_count(quantity: float | None, unit: str | None) -> int:
    if not quantity or quantity <= 0:
        return 1
    if (unit or "").strip().lower().rstrip(".") in _MEASURES:
        return 1
    return math.ceil(quantity)
