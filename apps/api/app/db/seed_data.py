"""Reference data for the sample-database generator: catalogue, brands, suppliers, geography.

Kept separate from the generation logic in ``app.db.seed`` so the simulation reads as rules and
this module reads as a catalogue. Nothing here is random; ``seed`` samples from it.
"""

from __future__ import annotations

from dataclasses import dataclass

# -- Catalogue --------------------------------------------------------------------------

# (name, parent name). Order matters: parents first; ids are assigned in this order.
CATEGORY_TREE: list[tuple[str, str | None]] = [
    ("Electronics", None),
    ("Computers", "Electronics"),
    ("Laptops", "Computers"),
    ("Monitors", "Computers"),
    ("Computer Accessories", "Computers"),
    ("Audio", "Electronics"),
    ("Headphones", "Audio"),
    ("Speakers", "Audio"),
    ("Smart Home", "Electronics"),
    ("Cameras", "Electronics"),
    ("Home & Kitchen", None),
    ("Kitchen", "Home & Kitchen"),
    ("Cookware", "Kitchen"),
    ("Small Appliances", "Kitchen"),
    ("Furniture", "Home & Kitchen"),
    ("Bedding", "Home & Kitchen"),
    ("Home Decor", "Home & Kitchen"),
    ("Apparel", None),
    ("Clothing", "Apparel"),
    ("Men's Clothing", "Clothing"),
    ("Women's Clothing", "Clothing"),
    ("Footwear", "Apparel"),
    ("Bags & Accessories", "Apparel"),
    ("Sports & Outdoors", None),
    ("Fitness", "Sports & Outdoors"),
    ("Camping", "Sports & Outdoors"),
    ("Cycling", "Sports & Outdoors"),
    ("Beauty", None),
    ("Skincare", "Beauty"),
    ("Haircare", "Beauty"),
    ("Books", None),
    ("Fiction", "Books"),
    ("Non-Fiction", "Books"),
    ("Toys & Games", None),
]


@dataclass(frozen=True)
class Leaf:
    """A leaf category and how its products behave."""

    department: str
    nouns: tuple[str, ...]
    price_range: tuple[float, float]
    weight_range: tuple[float, float]
    variant_kind: str  # apparel | shoes | tech | book | home
    return_rate: float  # per-line base probability of being returned
    season: str  # demand profile key in SEASONALITY


LEAVES: dict[str, Leaf] = {
    "Laptops": Leaf("Electronics", ("Ultrabook 13", "Ultrabook 14", "Pro Laptop 16",
                    "Gaming Laptop 15", "Chromebook 11", "Workstation 17"),
                    (449, 2599), (1.1, 2.8), "tech", 0.05, "tech"),
    "Monitors": Leaf("Electronics", ('27" 4K Monitor', '24" IPS Monitor',
                     '34" Ultrawide Monitor', '32" Curved Monitor'),
                     (149, 899), (3.5, 9.0), "tech", 0.05, "tech"),
    "Computer Accessories": Leaf("Electronics", ("Wireless Mouse", "Mechanical Keyboard",
                                 "USB-C Hub", "Laptop Stand", "1080p Webcam"),
                                 (15, 179), (0.1, 1.5), "tech", 0.06, "tech"),
    "Headphones": Leaf("Electronics", ("Noise-Cancelling Headphones", "Wireless Earbuds",
                       "Studio Headphones", "Sport Earbuds"),
                       (39, 429), (0.05, 0.4), "tech", 0.08, "tech"),
    "Speakers": Leaf("Electronics", ("Bluetooth Speaker", "Smart Speaker", "Soundbar",
                     "Bookshelf Speakers"), (35, 699), (0.4, 6.0), "tech", 0.05, "tech"),
    "Smart Home": Leaf("Electronics", ("Smart Plug 2-Pack", "Video Doorbell",
                       "Smart Thermostat", "Security Camera", "Smart Bulb 4-Pack"),
                       (19, 259), (0.1, 1.2), "tech", 0.06, "tech"),
    "Cameras": Leaf("Electronics", ("Mirrorless Camera", "Action Camera", "Instant Camera",
                    "50mm Prime Lens"), (89, 1799), (0.2, 1.2), "tech", 0.05, "tech"),
    "Cookware": Leaf("Home & Kitchen", ("Non-Stick Frying Pan", "Cast Iron Skillet",
                     "Stainless Saucepan Set", "Enameled Dutch Oven"),
                     (25, 319), (0.8, 6.5), "home", 0.04, "holiday"),
    "Small Appliances": Leaf("Home & Kitchen", ("Espresso Machine", "Air Fryer",
                             "High-Speed Blender", "Electric Kettle", "Stand Mixer"),
                             (29, 649), (1.0, 9.0), "home", 0.07, "holiday"),
    "Furniture": Leaf("Home & Kitchen", ("Ergonomic Office Chair", "Standing Desk",
                      "Oak Bookshelf", "Coffee Table", "Accent Armchair"),
                      (79, 899), (8.0, 35.0), "home", 0.06, "flat"),
    "Bedding": Leaf("Home & Kitchen", ("Cotton Sheet Set", "Down Comforter",
                    "Memory Foam Pillow", "Weighted Blanket"),
                    (25, 259), (0.8, 7.0), "home", 0.07, "winter"),
    "Home Decor": Leaf("Home & Kitchen", ("Table Lamp", "Round Wall Mirror", "Ceramic Vase",
                       "Wool Area Rug"), (19, 349), (0.5, 9.0), "home", 0.06, "holiday"),
    "Men's Clothing": Leaf("Apparel", ("Merino Sweater", "Oxford Shirt", "Slim Chinos",
                           "Rain Jacket", "Fleece Hoodie"),
                           (25, 219), (0.2, 0.9), "apparel", 0.24, "apparel"),
    "Women's Clothing": Leaf("Apparel", ("Linen Dress", "Cashmere Cardigan",
                             "High-Rise Jeans", "Puffer Jacket", "Silk Blouse"),
                             (29, 279), (0.2, 0.9), "apparel", 0.26, "apparel"),
    "Footwear": Leaf("Apparel", ("Running Shoes", "Leather Chelsea Boots", "Canvas Sneakers",
                     "Trail Running Shoes", "Recovery Slides"),
                     (29, 239), (0.4, 1.4), "shoes", 0.28, "apparel"),
    "Bags & Accessories": Leaf("Apparel", ("Leather Backpack", "Travel Duffel", "Wool Beanie",
                               "Polarized Sunglasses", "Leather Belt"),
                               (15, 259), (0.1, 1.6), "home", 0.08, "holiday"),
    "Fitness": Leaf("Sports & Outdoors", ("Yoga Mat", "Adjustable Dumbbells",
                    "Resistance Band Set", "Exercise Bike", "Foam Roller"),
                    (15, 899), (0.5, 38.0), "home", 0.07, "new_year"),
    "Camping": Leaf("Sports & Outdoors", ("2-Person Tent", "Down Sleeping Bag",
                    "Camping Stove", "Rechargeable Headlamp", "Insulated Bottle"),
                    (15, 449), (0.2, 3.5), "home", 0.06, "summer"),
    "Cycling": Leaf("Sports & Outdoors", ("Road Bike Helmet", "Bike Light Set",
                    "Cycling Jersey", "U-Lock"), (19, 179), (0.2, 1.4), "home", 0.07, "summer"),
    "Skincare": Leaf("Beauty", ("Vitamin C Serum", "Daily Moisturizer", "SPF 50 Sunscreen",
                     "Gentle Cleanser"), (9, 89), (0.1, 0.4), "home", 0.03, "summer"),
    "Haircare": Leaf("Beauty", ("Repair Shampoo", "Ionic Hair Dryer", "Styling Cream",
                     "Ceramic Hair Straightener"), (9, 259), (0.2, 1.0), "home", 0.05, "holiday"),
    "Fiction": Leaf("Books", ("The Glass Harbor", "Night Train to Lisbon", "Starfall Protocol",
                    "The Orchard Keeper", "A Quiet Inheritance"),
                    (9, 34), (0.3, 0.9), "book", 0.02, "holiday"),
    "Non-Fiction": Leaf("Books", ("The Lean Operator", "Salt & Smoke Cookbook",
                        "Empires of the Sea", "Deep Work Habits"),
                        (12, 44), (0.4, 1.2), "book", 0.02, "new_year"),
    "Toys & Games": Leaf("Toys & Games", ("Building Blocks Set", "Strategy Board Game",
                         "1000-Piece Puzzle", "RC Off-Road Car", "Plush Bear"),
                         (12, 159), (0.3, 2.5), "home", 0.05, "toys"),
}

# Monthly demand multipliers (index 0 = January) per seasonal profile.
SEASONALITY: dict[str, tuple[float, ...]] = {
    "flat": (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
    "tech": (0.8, 0.8, 0.9, 0.9, 0.9, 0.9, 1.0, 1.2, 1.1, 1.0, 1.5, 1.7),
    "holiday": (0.8, 0.8, 0.9, 0.9, 1.0, 0.9, 0.9, 0.9, 1.0, 1.1, 1.5, 1.9),
    "winter": (1.3, 1.1, 0.9, 0.8, 0.7, 0.7, 0.7, 0.8, 1.0, 1.2, 1.4, 1.5),
    "apparel": (0.9, 0.8, 1.1, 1.1, 1.0, 0.9, 0.9, 1.1, 1.2, 1.1, 1.3, 1.4),
    "new_year": (1.9, 1.4, 1.1, 1.0, 0.9, 0.8, 0.8, 0.8, 0.9, 0.9, 1.0, 1.2),
    "summer": (0.6, 0.6, 0.9, 1.1, 1.4, 1.7, 1.7, 1.4, 1.0, 0.8, 0.7, 0.8),
    "toys": (0.5, 0.5, 0.6, 0.7, 0.7, 0.7, 0.8, 0.8, 0.9, 1.2, 2.2, 3.0),
}

# Brands per department: (name, country, founded year).
BRANDS: dict[str, list[tuple[str, str, int]]] = {
    "Electronics": [("Voltix", "US", 2009), ("Lumora", "KR", 2001), ("Sonique", "JP", 1987),
                    ("Corelink", "TW", 1998), ("Nimbus Labs", "US", 2015)],
    "Home & Kitchen": [("Hearthstone", "US", 1972), ("Oakline", "DK", 1994),
                       ("Culina", "IT", 1958), ("Duvetta", "PT", 2006)],
    "Apparel": [("Northwind", "US", 1990), ("Stride Co.", "US", 2011),
                ("Atelier Nine", "FR", 2003), ("Kestrel", "GB", 1985)],
    "Sports & Outdoors": [("Summit Gear", "US", 1979), ("Pulse Fitness", "DE", 2008),
                          ("Velo Works", "NL", 1996)],
    "Beauty": [("Lumière", "FR", 1999), ("Verdant", "CA", 2014)],
    "Books": [("Penrose Press", "GB", 1946), ("Larkspur Books", "US", 1981)],
    "Toys & Games": [("BrightBlocks", "DK", 1962), ("Playwise", "US", 2005)],
}

# (name, country, lead time days, rating, departments served)
SUPPLIERS: list[tuple[str, str, int, float, tuple[str, ...]]] = [
    ("Shenzhen Brightway Electronics", "CN", 32, 4.1, ("Electronics",)),
    ("Hsinchu Precision Components", "TW", 28, 4.6, ("Electronics",)),
    ("Pacific Rim Audio", "VN", 35, 3.8, ("Electronics",)),
    ("Midwest Home Goods", "US", 9, 4.4, ("Home & Kitchen",)),
    ("Porto Textiles", "PT", 21, 4.5, ("Home & Kitchen", "Apparel")),
    ("Milano Cucina Forniture", "IT", 24, 4.2, ("Home & Kitchen",)),
    ("Dhaka Garment Works", "BD", 45, 3.6, ("Apparel",)),
    ("Saigon Footwear Co.", "VN", 40, 3.9, ("Apparel",)),
    ("Rocky Ridge Outfitters", "US", 12, 4.7, ("Sports & Outdoors",)),
    ("Bavaria Sport Supply", "DE", 16, 4.3, ("Sports & Outdoors",)),
    ("Lyon Cosmétiques", "FR", 18, 4.4, ("Beauty",)),
    ("Atlantic Book Distributors", "US", 7, 4.8, ("Books",)),
    ("Jutland Toy Makers", "DK", 20, 4.5, ("Toys & Games",)),
    ("Monterrey Manufacturing", "MX", 14, 3.7, ("Home & Kitchen", "Toys & Games")),
]

COLORS: dict[str, tuple[str, ...]] = {
    "apparel": ("Black", "Navy", "Heather Grey", "Olive", "Ivory", "Burgundy"),
    "shoes": ("Black", "White", "Tan", "Grey"),
    "tech": ("Black", "Silver", "White", "Space Grey", "Midnight Blue"),
    "home": ("Charcoal", "Natural", "White", "Sage", "Terracotta"),
}
APPAREL_SIZES: tuple[tuple[str, float], ...] = (("S", 0.8), ("M", 1.3), ("L", 1.2), ("XL", 0.7))
SHOE_SIZES: tuple[tuple[str, float], ...] = (
    ("7", 0.6), ("8", 1.0), ("9", 1.3), ("10", 1.3), ("11", 0.9), ("12", 0.5),
)

# -- Fulfilment and geography -----------------------------------------------------------

# (name, city, country)
WAREHOUSES: list[tuple[str, str, str]] = [
    ("Reno Fulfillment Center", "Reno", "US"),
    ("Columbus Fulfillment Center", "Columbus", "US"),
    ("Toronto Distribution Centre", "Mississauga", "CA"),
    ("Midlands Distribution Centre", "Coventry", "GB"),
    ("Rhine Logistics Hub", "Duisburg", "DE"),
    ("Sydney Distribution Centre", "Sydney", "AU"),
]


@dataclass(frozen=True)
class Country:
    weight: float  # share of customers
    currency: str
    tax_rate: float  # VAT/GST; US uses per-state rates instead
    cities: tuple[str, ...]
    streets: tuple[str, ...]
    carriers: tuple[tuple[str, float], ...]
    warehouse: int  # default fulfilling warehouse id (US is split by state)
    promised_days: int  # standard-service delivery promise


COUNTRIES: dict[str, Country] = {
    "US": Country(58, "USD", 0.0, (), ("Market St", "Oak Ave", "Maple Dr", "Cedar Ln",
                  "Washington Blvd", "Lake Rd", "Sunset Ave", "Park Pl"),
                  (("UPS", 0.4), ("FedEx", 0.3), ("USPS", 0.3)), 2, 5),
    "CA": Country(10, "CAD", 0.13, ("Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"),
                  ("King St W", "Yonge St", "Robson St", "Rue Sainte-Catherine"),
                  (("Canada Post", 0.6), ("UPS", 0.4)), 3, 6),
    "GB": Country(12, "GBP", 0.20, ("London", "Manchester", "Birmingham", "Edinburgh",
                  "Bristol", "Leeds"), ("High Street", "Church Road", "Station Road",
                  "Victoria Road"), (("Royal Mail", 0.6), ("DPD", 0.4)), 4, 3),
    "DE": Country(8, "EUR", 0.19, ("Berlin", "Munich", "Hamburg", "Cologne", "Frankfurt"),
                  ("Hauptstraße", "Bahnhofstraße", "Gartenweg", "Schillerstraße"),
                  (("DHL", 0.7), ("DPD", 0.3)), 5, 3),
    "FR": Country(6, "EUR", 0.20, ("Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux"),
                  ("Rue de la Paix", "Avenue Victor Hugo", "Rue du Moulin", "Boulevard Voltaire"),
                  (("DPD", 0.5), ("DHL", 0.5)), 5, 4),
    "AU": Country(6, "AUD", 0.10, ("Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"),
                  ("George St", "Collins St", "Queen St", "Hay St"),
                  (("Australia Post", 0.7), ("DHL", 0.3)), 6, 6),
}

# US states: (code, weight, cities, sales-tax rate, ships from the western warehouse)
US_STATES: list[tuple[str, float, tuple[str, ...], float, bool]] = [
    ("CA", 14, ("Los Angeles", "San Francisco", "San Diego", "Sacramento"), 0.0725, True),
    ("NY", 10, ("New York", "Buffalo", "Rochester"), 0.08, False),
    ("TX", 9, ("Austin", "Houston", "Dallas", "San Antonio"), 0.0625, True),
    ("FL", 7, ("Miami", "Orlando", "Tampa"), 0.06, False),
    ("WA", 5, ("Seattle", "Spokane", "Tacoma"), 0.065, True),
    ("IL", 5, ("Chicago", "Naperville"), 0.0625, False),
    ("PA", 4, ("Philadelphia", "Pittsburgh"), 0.06, False),
    ("GA", 4, ("Atlanta", "Savannah"), 0.04, False),
    ("MA", 3, ("Boston", "Cambridge"), 0.0625, False),
    ("CO", 3, ("Denver", "Boulder"), 0.029, True),
    ("AZ", 3, ("Phoenix", "Tucson"), 0.056, True),
    ("NJ", 3, ("Newark", "Jersey City"), 0.06625, False),
    ("NC", 3, ("Charlotte", "Raleigh"), 0.0475, False),
    ("OH", 3, ("Columbus", "Cleveland"), 0.0575, False),
    ("MI", 2, ("Detroit", "Ann Arbor"), 0.06, False),
    ("OR", 2, ("Portland", "Eugene"), 0.0, True),
]

# Carrier on-time reliability: probability a standard parcel arrives after its promise.
CARRIER_LATE_RATE: dict[str, float] = {
    "UPS": 0.07, "FedEx": 0.06, "USPS": 0.15, "Canada Post": 0.16, "Royal Mail": 0.12,
    "DPD": 0.09, "DHL": 0.07, "Australia Post": 0.17,
}

# Monthly FX starting points (USD per unit), random-walked month to month.
FX_START: dict[str, float] = {"EUR": 1.08, "GBP": 1.26, "CAD": 0.74, "AUD": 0.67}

# -- People -----------------------------------------------------------------------------

FIRST_NAMES: tuple[str, ...] = (
    "Olivia", "Liam", "Emma", "Noah", "Ava", "Oliver", "Sophia", "Elijah", "Isabella", "James",
    "Mia", "Lucas", "Amelia", "Mateo", "Harper", "Ethan", "Aria", "Aiden", "Chloe", "Leo",
    "Priya", "Arjun", "Mei", "Wei", "Yuki", "Hiro", "Fatima", "Omar", "Layla", "Yusuf",
    "Sofia", "Diego", "Valentina", "Santiago", "Camila", "Lukas", "Hannah", "Felix", "Lena",
    "Jonas", "Chloé", "Louis", "Manon", "Hugo", "Grace", "Jack", "Ruby", "Charlie", "Isla",
    "Thomas", "Zoe", "Daniel", "Nora", "Samuel", "Maya", "Kai", "Aisha", "Tariq", "Ingrid",
)
LAST_NAMES: tuple[str, ...] = (
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Martinez",
    "Lopez", "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Jackson", "Martin", "Lee",
    "Thompson", "White", "Harris", "Clark", "Lewis", "Walker", "Hall", "Young", "King",
    "Wright", "Scott", "Green", "Patel", "Shah", "Chen", "Wang", "Kim", "Nguyen", "Tanaka",
    "Sato", "Khan", "Hassan", "Rossi", "Müller", "Schmidt", "Schneider", "Fischer", "Dubois",
    "Moreau", "Laurent", "O'Brien", "Murphy", "Campbell", "Stewart", "Kowalski", "Novak",
    "Silva", "Santos", "Haddad", "Okafor", "Mensah", "Larsen",
)
EMAIL_DOMAINS: tuple[str, ...] = ("example.com", "mail.example", "inbox.example", "example.org")

# -- Text -------------------------------------------------------------------------------

REVIEW_TITLES: dict[int, tuple[str, ...]] = {
    5: ("Absolutely love it", "Exceeded expectations", "Best purchase this year", "Perfect"),
    4: ("Very good", "Solid choice", "Happy with it", "Great value"),
    3: ("It's okay", "Does the job", "Mixed feelings", "Average"),
    2: ("Not great", "Disappointing quality", "Expected more"),
    1: ("Do not buy", "Broke within a week", "Waste of money"),
}
REVIEW_BODIES: dict[int, tuple[str, ...]] = {
    5: ("Exactly as described and the quality is excellent.",
        "Arrived quickly and works perfectly. Would buy again.",
        "Great build quality, worth every penny."),
    4: ("Good product overall, a few minor quirks.",
        "Does what it says. Packaging could be better.",
        "Very happy, though it took a while to arrive."),
    3: ("Fine for the price, nothing special.",
        "Works, but the finish feels a bit cheap.",
        "Some good points, some bad."),
    2: ("Quality is lower than the photos suggest.",
        "Stopped working properly after a few weeks.",
        "Sizing was off and the material feels thin."),
    1: ("Arrived damaged and support was slow to respond.",
        "Completely different from the description.",
        "Fell apart almost immediately."),
}
