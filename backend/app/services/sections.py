"""Supermarket aisle sections for the shopping list.

Sections are derived from the item *name*, not stored on the shopping_items row.
That way items imported from meal planning get classified for free, and the
GROUP BY aggregation in the shopping list query stays untouched.

Classification is fully automatic: item names are matched in English, German
and Dutch, with a fuzzy fallback for misspellings.

Note: "market" here means the supermarket chain (Lidl / Albert Heijn), which is
a view-level concept only. It is NOT the shopping_items.store column — that one
holds the top-level category (supermarket / household / custom).
"""

import difflib
import re
import unicodedata
from functools import lru_cache

# slug, label — this order is the default aisle order for every market
SECTIONS: list[tuple[str, str]] = [
    ("Fruit & Veggies", "Fruit & Veggies"),
    ("bakery", "Bakery"),
    ("dairy", "Dairy & Eggs"),
    ("deli", "Cold Cuts & Deli"),
    ("meat_fish", "Meat & Fish"),
    ("frozen", "Frozen"),
    ("pantry", "Pantry & Dry Goods"),
    ("canned", "Canned & Jars"),
    ("baking", "Spices & Baking"),
    ("drinks", "Drinks"),
    ("snacks", "Snacks & Sweets"),
    ("cleaning", "Household & Cleaning"),
    ("other", "Other"),
]

SECTION_SLUGS = [slug for slug, _ in SECTIONS]
DEFAULT_SECTION = "other"

MARKETS: list[tuple[str, str]] = [
    ("lidl", "Lidl"),
    ("ah", "Albert Heijn"),
]

MARKET_SLUGS = [slug for slug, _ in MARKETS]
DEFAULT_MARKET = MARKET_SLUGS[0]

# Keywords are folded (lowercased, umlauts stripped, ß -> ss) before matching,
# so "müsli" and "musli" are the same keyword. Common alternative spellings
# that folding does NOT unify ("muesli") are listed explicitly.
KEYWORDS: dict[str, list[str]] = {
    "Fruit & Veggies": [
        # en
        "apple", "apricot", "artichoke", "arugula", "asparagus", "aubergine",
        "avocado", "banana", "basil", "beetroot", "bell pepper", "berries",
        "blackberr", "blueberr", "bok choy", "broccoli", "brussels sprout",
        "cabbage", "carrot", "cauliflower", "celery", "chard", "cherr",
        "chili", "chilli", "chive", "cilantro", "coriander", "corn on the cob",
        "courgette", "cucumber", "dill", "eggplant", "endive", "fennel",
        "fresh ginger", "garlic", "grape", "green bean", "green onion",
        "iceberg", "kale", "kiwi", "leek", "lemon", "lettuce", "lime",
        "mandarin", "mango", "melon", "mint", "mushroom", "nectarine",
        "onion", "orange", "oregano", "parsley", "parsnip", "peach", "pear",
        "pepper", "pineapple", "plum", "pomegranate", "potato", "pumpkin",
        "radish", "raspberr", "rhubarb", "rocket", "rosemary", "sage",
        "scallion", "shallot", "spinach", "spring onion", "sprout",
        "strawberr", "sweet potato", "thyme", "tomato", "watermelon",
        "zucchini",
        # de
        "ananas", "apfel", "äpfel", "aprikose", "artischocke", "basilikum",
        "birne", "blaubeer", "blumenkohl", "brombeer", "brokkoli",
        "champignon", "chicoree", "eisberg", "erdbeer", "feldsalat",
        "fenchel", "grüne bohnen", "grünkohl", "gurke", "heidelbeer",
        "himbeer", "ingwer", "johannisbeer", "karotte", "kartoffel", "kirsche",
        "knoblauch", "kohl", "kohlrabi", "kopfsalat", "kräuter", "kürbis",
        "lauch", "limette", "mandarine", "melone", "minze", "möhre",
        "nektarine", "paprika", "petersilie", "pfirsich", "pflaume", "pilz",
        "porree", "radieschen", "rosenkohl", "rosmarin", "rote bete",
        "rucola", "salat", "schnittlauch", "sellerie", "spargel", "spinat",
        "sprossen", "süßkartoffel", "suesskartoffel", "thymian", "tomate",
        "trauben", "wassermelone", "weintrauben", "zitrone", "zwiebel",
        # nl
        "aardappel", "aardbei", "appel", "asperge", "aubergine", "banaan",
        "bieslook", "bleekselderij", "bloemkool", "boerenkool", "bosbes",
        "braam", "brambo", "citroen", "druiven", "framboos", "gember",
        "groene bonen", "ijsberg", "kers", "knoflook", "komkommer",
        "kropsla", "limoen", "mandarijn", "meloen", "munt", "nectarine",
        "paddenstoel", "peer", "peterselie", "perzik", "pompoen", "prei",
        "pruim", "radijs", "rabarber", "rode bieten", "rode ui", "rozemarijn",
        "sinaasappel", "sla", "sperziebonen", "spinazie", "spruitjes",
        "tijm", "tomaat", "tomaten", "ui", "uien", "uitjes", "venkel",
        "watermeloen", "witlof", "wortel", "zoete aardappel",
    ],
    "bakery": [
        # en
        "baguette", "bagel", "bread", "brioche", "bun", "ciabatta",
        "croissant", "crumpet", "danish", "flatbread", "focaccia", "muffin",
        "naan", "pita", "pitta", "pretzel", "roll", "rye", "scone",
        "sourdough", "tortilla wrap", "wrap",
        # de
        "brezel", "brot", "brötchen", "broetchen", "hörnchen", "knäckebrot",
        "sauerteig", "semmel", "toast", "vollkornbrot", "zwieback",
        # nl
        "beschuit", "boterham", "bolletje", "brood", "knackebrod",
        "pistolet", "stokbrood", "volkoren",
    ],
    "dairy": [
        # en
        "brie", "butter", "buttermilk", "camembert", "cheddar", "cheese",
        "cottage cheese", "cream", "cream cheese", "creme fraiche",
        "crème fraîche", "curd", "custard", "egg", "feta", "goat cheese",
        "gouda", "greek yogurt", "gruyere", "halloumi", "havarti",
        "mascarpone", "milk", "mozzarella", "oat milk", "parmesan",
        "pecorino", "quark", "ricotta", "skyr", "soy milk", "sour cream",
        "whipping cream", "yoghurt", "yogurt",
        # de
        "buttermilch", "eier", "frischkäse", "hafermilch", "hüttenkäse",
        "joghurt", "jogurt", "käse", "kaese", "milch", "sahne", "sauerrahm",
        "schlagsahne", "schmand", "sojamilch",
        # nl
        "boter", "eieren", "eitjes", "geitenkaas", "havermelk", "kaas",
        "karnemelk", "kwark", "melk", "room", "roomkaas", "slagroom",
        "sojamelk", "vla", "yoghurt", "zure room",
    ],
    "deli": [
        # en
        "bacon", "bologna", "cold cut", "deli meat", "ham", "liver pate",
        "mortadella", "pancetta", "pastrami", "pate", "pepperoni",
        "prosciutto", "salami", "smoked ham",
        # de
        "aufschnitt", "bierschinken", "cabanossi", "fleischwurst",
        "gelbwurst", "katenschinken", "kochschinken", "landjäger",
        "leberwurst", "lyoner", "mettwurst", "salami", "schinken", "speck",
        "streichwurst", "teewurst",
        # nl
        "achterham", "boterhamworst", "cervelaat", "filet americain",
        "gerookte ham", "leverworst", "rookvlees", "smeerworst",
        "snijworst", "vleeswaren",
    ],
    "meat_fish": [
        # en
        "anchov", "beef", "burger patt", "chicken", "chorizo",
        "cod", "duck", "fillet", "fish", "ground beef", "haddock",
        "lamb", "meatball", "mince", "mussel", "pork",
        "prawn", "salmon", "sardine", "sausage",
        "scampi", "seafood", "shrimp", "steak", "tilapia", "trout", "tuna",
        "turkey", "veal",
        # de
        "bratwurst", "ente", "fisch", "forelle", "frikadelle", "garnelen",
        "hack", "hackfleisch", "hähnchen", "haehnchen", "hühnchen", "huhn",
        "kabeljau", "lachs", "lamm", "muscheln", "pute", "rind",
        "rindfleisch", "schnitzel", "schwein",
        "thunfisch", "truthahn", "wurst", "würstchen",
        # nl
        "biefstuk", "eend", "filet", "garnalen", "gehakt", "kabeljauw",
        "kalkoen", "kip", "lamsvlees", "mosselen", "rundvlees",
        "speklapjes", "tonijn", "varkensvlees", "vis", "worst", "zalm",
    ],
    "frozen": [
        # en
        "frozen", "ice cream", "sorbet", "puff pastry", "fish stick",
        "fish finger", "french fries", "oven fries",
        # de
        "blätterteig", "eis", "eiscreme", "fischstäbchen", "pommes",
        "tiefkühl", "tiefgekühlt",
        # nl
        "bladerdeeg", "diepvries", "friet", "ijs", "patat", "roomijs",
        "vissticks",
    ],
    "pantry": [
        # en
        "barley", "basmati", "breadcrumb", "bulgur", "cereal", "couscous",
        "crouton", "farro", "granola", "lasagne sheet", "lentil", "linguine",
        "macaroni", "muesli", "noodle", "oat", "orzo", "pasta", "penne",
        "polenta", "quinoa", "ramen", "ravioli", "rice", "risotto",
        "spaghetti", "split pea", "tagliatelle", "tortellini", "vermicelli",
        # de
        "cornflakes", "grieß", "haferflocken", "lasagneplatten", "linsen",
        "makkaroni", "müsli", "nudeln", "paniermehl", "reis",
        "semmelbrösel",
        # nl
        "havermout", "linzen", "macaroni", "mie", "noedels",
        "ontbijtgranen", "paneermeel", "rijst",
    ],
    "canned": [
        # en
        "baked bean", "black bean", "borlotti", "broth", "butter bean",
        "cannellini", "canned", "capers", "chickpea", "coconut milk",
        "gherkin", "hummus", "jam", "kidney bean", "ketchup", "mayonnaise",
        "mustard", "olive", "passata", "peanut butter", "pesto", "pickle",
        "salsa", "sauce", "soy sauce", "stock", "sundried tomato",
        "sun-dried tomato", "tahini", "tinned", "tomato paste",
        "tomato puree", "tuna can", "vinegar",
        # de
        "bohnen", "brühe", "dose", "essig", "gemüsebrühe", "gewürzgurken",
        "kichererbsen", "kokosmilch", "konfitüre", "konserve", "mais",
        "majonäse", "marmelade", "oliven", "passierte tomaten", "senf",
        "sojasoße", "sojasauce", "soße", "tomatenmark",
        # nl
        "appelmoes", "augurken", "azijn", "blik", "bonen", "bouillon",
        "gepelde tomaten", "kikkererwten", "kokosmelk", "mayonaise",
        "mosterd", "olijven", "pindakaas", "saus", "sojasaus",
        "tomatenpuree",
    ],
    "baking": [
        # en
        "almond", "baking powder", "baking soda", "bay leaf", "cashew",
        "chia", "cinnamon", "cocoa", "cornstarch", "cumin", "curry powder",
        "flour", "ginger", "hazelnut", "honey", "icing sugar", "maple syrup",
        "nutmeg", "olive oil", "paprika powder", "peanut", "pecan",
        "pine nut", "pistachio", "poppy seed", "salt", "seasoning", "sesame",
        "spice", "sugar", "sunflower oil", "sunflower seed", "turmeric",
        "vanilla", "walnut", "yeast",
        # de
        "ahornsirup", "backpulver", "cashewkerne", "gewürz", "haselnüsse",
        "hefe", "honig", "kakao", "kreuzkümmel", "kurkuma", "lorbeer",
        "mandeln", "mehl", "muskat", "natron", "olivenöl", "paprikapulver",
        "pfeffer", "puderzucker", "rapsöl", "salz", "sesam", "sonnenblumenöl",
        "speiseöl", "speisestärke", "vanille", "walnüsse", "zimt", "zucker",
        # nl
        "ahornsiroop", "amandelen", "bakpoeder", "bloem", "cashewnoten",
        "gist", "hazelnoten", "honing", "kaneel", "kerrie", "komijn",
        "kruiden", "laurier", "maizena", "nootmuskaat", "olie", "olijfolie",
        "peper", "poedersuiker", "suiker", "walnoten", "zonnebloemolie",
        "zout",
    ],
    "drinks": [
        # en
        "beer", "cider", "coffee", "cola", "espresso", "juice", "lemonade",
        "prosecco", "soda", "sparkling water", "tea", "tonic", "water",
        "wine",
        # de
        "apfelsaft", "bier", "kaffee", "limonade", "mineralwasser",
        "orangensaft", "rotwein", "saft", "sekt", "sprudel", "tee", "wasser",
        "wein", "weißwein",
        # nl
        "appelsap", "bronwater", "frisdrank", "koffie", "rode wijn", "sap",
        "sinaasappelsap", "spuitwater", "thee", "witte wijn", "wijn",
    ],
    "snacks": [
        # en
        "biscuit", "candy", "chip", "chocolate", "cookie", "cracker",
        "crisps", "dark chocolate", "milk chocolate", "nachos", "popcorn",
        "pretzel snack", "sweets", "tortilla chip", "trail mix",
        # de
        "gummibärchen", "kekse", "kuchen", "riegel", "salzstangen",
        "schokolade", "süßigkeiten", "waffeln",
        # nl
        "chocolade", "drop", "gebak", "koek", "koekjes", "pinda's",
        "snoep", "stroopwafel", "zoutjes",
    ],
    "cleaning": [
        # en
        "aluminium foil", "aluminum foil", "baking paper", "bin bag",
        "bleach", "cleaner", "cling film", "deodorant", "detergent",
        "dish soap", "dishwasher tab", "floor cleaner", "garbage bag",
        "kitchen roll", "laundry", "napkin", "paper towel", "shampoo",
        "shower gel", "soap", "sponge", "tissue", "toilet paper",
        "toothpaste", "trash bag", "washing up",
        # de
        "alufolie", "backpapier", "duschgel", "frischhaltefolie",
        "klopapier", "küchenrolle", "müllbeutel", "müllsäcke", "putzmittel",
        "reiniger", "schwamm", "seife", "servietten", "spülmaschinentabs",
        "spülmittel", "taschentücher", "toilettenpapier", "waschmittel",
        "weichspüler", "zahnpasta",
        # nl
        "afwasmiddel", "allesreiniger", "aluminiumfolie", "bakpapier",
        "douchegel", "keukenrol", "schoonmaakmiddel", "servetten", "spons",
        "tandpasta", "vaatwastabletten", "vershoudfolie", "vuilniszakken",
        "wasmiddel", "wasverzachter", "wc-papier", "zakdoekjes", "zeep",
    ],
}


def _fold(text: str) -> str:
    """Lowercase and strip diacritics so 'Müsli' and 'musli' compare equal."""
    text = text.lower().replace("ß", "ss")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalise(name: str) -> str:
    return " ".join(_fold(name).strip().split())


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Match German/Dutch compounds without matching random substrings.

    Keywords of 5+ characters match anywhere, so "milch" catches "Vollmilch"
    and "worst" catches "knakworst". Shorter ones must sit at a word start or
    a word end, so "oat" catches "oats" and "milchreis" but not "tomoatoes".
    """
    escaped = re.escape(keyword)
    if len(keyword) >= 5:
        return re.compile(escaped)
    return re.compile(rf"\b{escaped}|{escaped}\b")


# Longest keyword first so "buttermilk" beats "butter", "milk chocolate" beats
# "milk", and "kokosmelk" beats "melk".
_RULES: list[tuple[re.Pattern[str], str]] = [
    (_keyword_pattern(kw), slug)
    for kw, slug in sorted(
        ((_fold(kw), slug) for slug, kws in KEYWORDS.items() for kw in kws),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
]

# Single-word keywords long enough to fuzzy-match a typo against.
_FUZZY_WORDS: dict[str, str] = {}
for _slug, _kws in KEYWORDS.items():
    for _kw in _kws:
        _folded = _fold(_kw)
        if " " not in _folded and len(_folded) >= 5:
            _FUZZY_WORDS.setdefault(_folded, _slug)
_FUZZY_KEYS = list(_FUZZY_WORDS)


@lru_cache(maxsize=2048)
def _classify_rules(key: str) -> str:
    """Keyword match, then a fuzzy pass for misspellings."""
    for pattern, slug in _RULES:
        if pattern.search(key):
            return slug

    for word in re.findall(r"[a-z0-9']+", key):
        if len(word) < 5:
            continue
        close = difflib.get_close_matches(word, _FUZZY_KEYS, n=1, cutoff=0.8)
        if close:
            return _FUZZY_WORDS[close[0]]

    return DEFAULT_SECTION


def classify(name: str) -> str:
    """Resolve an item name to a section slug."""
    return _classify_rules(normalise(name))


async def load_orders(db) -> dict[str, list[str]]:
    """Section order per market: saved order first, then any unsaved sections."""
    async with db.execute(
        "SELECT market, section FROM shopping_section_order ORDER BY market, position"
    ) as cursor:
        rows = await cursor.fetchall()

    saved: dict[str, list[str]] = {}
    for row in rows:
        if row["section"] in SECTION_SLUGS:
            saved.setdefault(row["market"], []).append(row["section"])

    orders: dict[str, list[str]] = {}
    for market in MARKET_SLUGS:
        order = saved.get(market, [])
        orders[market] = order + [s for s in SECTION_SLUGS if s not in order]
    return orders
