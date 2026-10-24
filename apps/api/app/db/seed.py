"""Deterministic seed data for the sample e-commerce database.

Simulates ~45 months of trading for an international online retailer with a fixed RNG seed, so
every build produces an identical database (reproducible tests, demos and evals). The
simulation keeps the data internally consistent rather than independently random:

* order lines are priced from the product's price history on the order date, converted to the
  order currency with that month's exchange rate;
* demand follows growth, seasonality (Black Friday, holidays, summer) and a long tail of repeat
  buyers, and products only sell between their listing and discontinuation dates;
* fulfilment drives the status timeline: payment (with occasional failures), shipping, late
  deliveries, returns and refunds; late or damaged parcels raise support tickets;
* loyalty tiers are derived from each customer's lifetime spend.

Everything is generated in memory first, then inserted parent-first to satisfy foreign keys.
Reference data (catalogue, brands, geography) lives in ``app.db.seed_data``.
"""

from __future__ import annotations

import bisect
import math
import random
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from app.db import seed_data as ref

SEED = 42
START = datetime(2023, 1, 1)  # store launch; first orders
END = datetime(2026, 9, 30, 23, 59, 59)  # "now" for the dataset
SIGNUP_START = datetime(2022, 9, 1)  # pre-launch newsletter signups

# Volumes (exported so tests can assert against them without hard-coding magic numbers).
N_CUSTOMERS = 2500
N_ORDERS = 8000
N_ABANDONED_CARTS = 10000
N_WISHLIST_ATTEMPTS = 4000
N_UNVERIFIED_REVIEWS = 250
N_GENERAL_TICKETS = 500

_MONTH_FACTOR = (0.85, 0.8, 0.95, 0.95, 1.0, 1.02, 1.08, 1.0, 0.95, 1.0, 1.45, 1.75)
_WEEKDAY_FACTOR = (1.0, 0.97, 0.97, 1.0, 1.05, 1.12, 1.15)
_HOUR_WEIGHTS = (0.3, 0.2, 0.15, 0.1, 0.1, 0.2, 0.4, 0.7, 1.0, 1.1, 1.2, 1.3, 1.4, 1.3, 1.2, 1.2,
                 1.3, 1.5, 1.8, 2.1, 2.3, 2.0, 1.4, 0.8)
_PAY_METHODS = (("card", 55), ("paypal", 20), ("apple_pay", 14), ("bank_transfer", 6),
                ("gift_card", 5))
_TICKET_PRIORITY = {
    "shipping_delay": (("medium", 6), ("high", 4)),
    "damaged_item": (("high", 7), ("urgent", 3)),
    "payment_issue": (("high", 6), ("urgent", 4)),
    "return_request": (("low", 5), ("medium", 5)),
    "product_question": (("low", 8), ("medium", 2)),
    "account": (("low", 5), ("medium", 5)),
}
_TICKET_RESOLVE_DAYS = {
    "shipping_delay": (1.0, 5.0), "damaged_item": (1.0, 6.0), "payment_issue": (0.2, 2.0),
    "return_request": (1.0, 8.0), "product_question": (0.1, 1.5), "account": (0.1, 3.0),
}
_PRIORITY_ORDER = ("low", "medium", "high", "urgent")
Row = tuple[object, ...]
_PayFn = Callable[[float, str, datetime], None]

_APPAREL_REASONS = (("too_small", 30), ("too_large", 24), ("not_as_described", 14),
                    ("changed_mind", 16), ("defective", 5), ("damaged_in_transit", 5),
                    ("wrong_item", 6))
_GOODS_REASONS = (("defective", 30), ("not_as_described", 18), ("changed_mind", 22),
                  ("damaged_in_transit", 14), ("wrong_item", 10))


def _ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _d(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _month(value: date) -> str:
    return value.strftime("%Y-%m-01")


def _money(value: float) -> float:
    return round(value, 2)


def _charm(value: float) -> float:
    """Round a price to a retail .99 ending."""
    return max(round(value) - 0.01, 0.99)


def _black_friday(year: int) -> date:
    first = date(year, 11, 1)
    first_thursday = first + timedelta(days=(3 - first.weekday()) % 7)
    return first_thursday + timedelta(days=22)


def _is_peak(day: date) -> bool:
    return (day.month == 11 and day.day >= 20) or day.month == 12


def _in_sale(day: date) -> bool:
    offset = (day - _black_friday(day.year)).days
    return (
        -4 <= offset <= 3
        or (day.month == 12 and day.day <= 20)
        or (day.month == 7 and 9 <= day.day <= 11)
        or (day.month == 1 and 2 <= day.day <= 10)
    )


def _weighted[T](rng: random.Random, options: tuple[tuple[T, float], ...]) -> T:
    values = [value for value, _ in options]
    weights = [weight for _, weight in options]
    return rng.choices(values, weights=weights)[0]


def _pick_prefix(rng: random.Random, cum_weights: list[float], k: int) -> int:
    """Index of a weighted pick among the first ``k`` items, given cumulative weights."""
    target = rng.random() * cum_weights[k - 1]
    return min(bisect.bisect_right(cum_weights, target, 0, k), k - 1)


# -- In-memory entities -------------------------------------------------------------------


@dataclass
class Product:
    id: int
    sku: str
    name: str
    category_id: int
    leaf: ref.Leaf
    brand_id: int
    supplier_id: int
    cost_ratio: float
    weight_kg: float
    created: date
    discontinued: date | None
    popularity: float
    quality: float  # hidden 0..1 driver of ratings and returns
    history: list[tuple[date, float]]  # (valid_from, USD price), ascending
    variant_ids: list[int] = field(default_factory=list)
    variant_weights: list[float] = field(default_factory=list)

    @property
    def price(self) -> float:
        return self.history[-1][1]

    def price_on(self, day: date) -> float:
        index = bisect.bisect_right([start for start, _ in self.history], day) - 1
        return self.history[max(index, 0)][1]

    def sells_on(self, day: date) -> bool:
        return self.created <= day and (self.discontinued is None or day < self.discontinued)


@dataclass
class Variant:
    id: int
    product: Product
    sku: str
    color: str | None
    size: str | None
    multiplier: float


@dataclass
class Customer:
    id: int
    name: str
    email: str
    phone: str | None
    country: str
    state: str | None
    city: str
    segment: str
    channel: str
    referred_by: int | None
    opt_in: bool
    created: datetime
    propensity: float
    shipping_address_id: int = 0
    billing_address_id: int = 0
    order_count: int = 0
    lifetime_usd: float = 0.0


@dataclass
class Line:
    id: int
    variant: Variant
    quantity: int
    unit_price: float
    discount: float

    @property
    def net(self) -> float:
        """Unrounded line net; order subtotals round once, as ROUND(SUM(...), 2) does in SQL."""
        return self.quantity * self.unit_price * (1 - self.discount)


@dataclass
class Coupon:
    id: int
    code: str
    description: str
    percent_off: int
    min_order_amount: float
    active: bool
    valid_from: date
    valid_to: date

    def valid_on(self, day: date) -> bool:
        return self.active and self.valid_from <= day <= self.valid_to


@dataclass
class Campaign:
    id: int
    name: str
    channel: str
    start: date
    end: date
    budget: float


@dataclass
class ReturnCase:
    order_id: int
    status: str
    reason: str
    requested_at: datetime
    resolved_at: datetime | None
    refund_amount: float | None
    items: list[tuple[int, int, str]]  # (order_item_id, quantity, condition)


@dataclass
class TicketSeed:
    customer_id: int
    order_id: int | None
    category: str
    created_at: datetime


# -- Simulation ---------------------------------------------------------------------------


class _World:
    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.rows: dict[str, Sequence[Row]] = {}
        self.categories: dict[str, int] = {}
        self.products: list[Product] = []
        self.variants: dict[int, Variant] = {}
        self.customers: list[Customer] = []
        self.coupons: list[Coupon] = []
        self.campaigns: list[Campaign] = []
        self.fx: dict[tuple[str, str], float] = {}
        self.active_cache: dict[date, tuple[list[Product], list[float]]] = {}
        self.tickets: list[TicketSeed] = []
        self.reviewed: set[tuple[int, int]] = set()  # (customer_id, product_id)
        self.returned_lines: set[int] = set()

    # -- reference tables --------------------------------------------------------------

    def build_reference(self) -> None:
        rows: list[Row] = []
        for index, (name, parent) in enumerate(ref.CATEGORY_TREE, start=1):
            self.categories[name] = index
            rows.append((index, name, self.categories[parent] if parent else None, "2022-08-01"))
        self.rows["categories"] = rows

        brand_rows: list[Row] = []
        self.brand_ids: dict[str, list[int]] = {}
        for department, brands in ref.BRANDS.items():
            for name, country, founded in brands:
                brand_id = len(brand_rows) + 1
                brand_rows.append((brand_id, name, country, founded))
                self.brand_ids.setdefault(department, []).append(brand_id)
        self.rows["brands"] = brand_rows

        supplier_rows: list[Row] = []
        self.supplier_ids: dict[str, list[int]] = {}
        for index, (name, country, lead, rating, departments) in enumerate(ref.SUPPLIERS, 1):
            slug = "".join(ch for ch in name.lower() if ch.isalnum())[:14]
            supplier_rows.append(
                (index, name, country, f"orders@{slug}.example", lead, rating, "2022-06-01")
            )
            for department in departments:
                self.supplier_ids.setdefault(department, []).append(index)
        self.lead_times = {i: s[2] for i, s in enumerate(ref.SUPPLIERS, 1)}
        self.rows["suppliers"] = supplier_rows

        self.rows["warehouses"] = [
            (i, name, city, country) for i, (name, city, country) in enumerate(ref.WAREHOUSES, 1)
        ]

        # Monthly exchange rates as a gentle random walk.
        rates = dict(ref.FX_START)
        fx_rows: list[Row] = []
        month = date(SIGNUP_START.year, SIGNUP_START.month, 1)
        while month <= END.date():
            key = _month(month)
            self.fx[("USD", key)] = 1.0
            fx_rows.append(("USD", key, 1.0))
            for currency in rates:
                rates[currency] *= math.exp(self.rng.gauss(0, 0.012))
                self.fx[(currency, key)] = round(rates[currency], 4)
                fx_rows.append((currency, key, round(rates[currency], 4)))
            month = (month + timedelta(days=32)).replace(day=1)
        self.rows["exchange_rates"] = fx_rows

    # -- catalogue ----------------------------------------------------------------------

    def build_catalogue(self) -> None:
        rng = self.rng
        product_rows: list[Row] = []
        history_rows: list[Row] = []
        variant_rows: list[Row] = []
        for leaf_name, leaf in ref.LEAVES.items():
            brands = self.brand_ids[leaf.department]
            for noun in leaf.nouns:
                count = 1 if leaf.variant_kind == "book" or rng.random() < 0.5 else 2
                for brand_id in rng.sample(brands, count):
                    product = self._make_product(leaf_name, leaf, noun, brand_id)
                    self.products.append(product)
                    product_rows.append((
                        product.id, product.sku, product.name, product.category_id,
                        product.brand_id, product.supplier_id, product.price,
                        _money(product.price * product.cost_ratio), product.weight_kg,
                        0 if product.discontinued else 1, _d(product.created),
                        _d(product.discontinued) if product.discontinued else None,
                    ))
                    for i, (start, price) in enumerate(product.history):
                        end = product.history[i + 1][0] if i + 1 < len(product.history) else None
                        history_rows.append((
                            len(history_rows) + 1, product.id, price, _d(start),
                            _d(end) if end else None,
                        ))
                    for variant, weight in self._make_variants(product):
                        self.variants[variant.id] = variant
                        product.variant_ids.append(variant.id)
                        product.variant_weights.append(weight)
                        variant_rows.append((
                            variant.id, product.id, variant.sku, variant.color, variant.size,
                            _money(product.price * variant.multiplier), _d(product.created),
                        ))
        self.rows["products"] = product_rows
        self.rows["product_price_history"] = history_rows
        self.rows["product_variants"] = variant_rows

    def _make_product(self, leaf_name: str, leaf: ref.Leaf, noun: str, brand_id: int) -> Product:
        rng = self.rng
        product_id = len(self.products) + 1
        brand_name = self.rows["brands"][brand_id - 1][1]
        name = noun if leaf.variant_kind == "book" else f"{brand_name} {noun}"
        if rng.random() < 0.62:
            created = date(2022, 9, 1) + timedelta(days=rng.randint(0, 120))
        else:
            created = START.date() + timedelta(days=rng.randint(0, (END - START).days - 90))
        discontinued = None
        if rng.random() < 0.07:
            earliest = created + timedelta(days=200)
            latest = END.date() - timedelta(days=20)
            if earliest < latest:
                discontinued = earliest + timedelta(days=rng.randint(0, (latest - earliest).days))

        low, high = leaf.price_range
        price = _charm(low * math.exp(rng.random() * math.log(high / low)))
        history = [(created, price)]
        change_days = sorted(
            created + timedelta(days=rng.randint(30, max(31, (END.date() - created).days - 10)))
            for _ in range(_weighted(rng, ((0, 30), (1, 35), (2, 25), (3, 10))))
        )
        for day in change_days:
            if day > history[-1][0]:
                price = _charm(price * rng.uniform(0.86, 1.16))
                history.append((day, price))

        department_code = leaf.department[:3].upper()
        low_kg, high_kg = leaf.weight_range
        return Product(
            id=product_id,
            sku=f"{department_code}-{product_id:05d}",
            name=name,
            category_id=self.categories[leaf_name],
            leaf=leaf,
            brand_id=brand_id,
            supplier_id=rng.choice(self.supplier_ids[leaf.department]),
            cost_ratio=rng.uniform(0.32, 0.62),
            weight_kg=round(rng.uniform(low_kg, high_kg), 2),
            created=created,
            discontinued=discontinued,
            popularity=rng.lognormvariate(0, 0.9),
            quality=rng.uniform(0.55, 1.0),
            history=history,
        )

    def _make_variants(self, product: Product) -> list[tuple[Variant, float]]:
        rng = self.rng
        kind = product.leaf.variant_kind
        options: list[tuple[str | None, str | None, float, float]] = []
        if kind == "apparel":
            for color in rng.sample(ref.COLORS["apparel"], 3 if rng.random() < 0.3 else 2):
                options += [(color, size, 1.0, w) for size, w in ref.APPAREL_SIZES]
        elif kind == "shoes":
            for color in rng.sample(ref.COLORS["shoes"], rng.randint(1, 2)):
                options += [(color, size, 1.0, w) for size, w in ref.SHOE_SIZES]
        elif kind == "book":
            options.append((None, "Paperback", 1.0, 3.0))
            if rng.random() < 0.7:
                options.append((None, "Hardcover", 1.65, 1.0))
        elif kind == "tech":
            for i, color in enumerate(rng.sample(ref.COLORS["tech"], rng.randint(1, 3))):
                options.append((color, None, 1.0 if i == 0 else 1.05, 2.0 if i == 0 else 1.0))
        elif rng.random() < 0.4:
            options.append((None, None, 1.0, 1.0))
        else:
            for color in rng.sample(ref.COLORS["home"], rng.randint(1, 2)):
                options.append((color, None, 1.0, 1.0))

        variants: list[tuple[Variant, float]] = []
        for n, (shade, size, multiplier, weight) in enumerate(options, start=1):
            variant_id = len(self.variants) + len(variants) + 1
            variants.append((
                Variant(variant_id, product, f"{product.sku}-{n:02d}", shade, size, multiplier),
                weight,
            ))
        return variants

    def active_products(self, day: date) -> tuple[list[Product], list[float]]:
        cached = self.active_cache.get(day)
        if cached is None:
            products = [p for p in self.products if p.sells_on(day)]
            cum: list[float] = []
            total = 0.0
            for product in products:
                season = ref.SEASONALITY[product.leaf.season][day.month - 1]
                affordability = (100 / (product.price_on(day) + 20)) ** 0.85
                total += product.popularity * season * affordability
                cum.append(total)
            cached = (products, cum)
            self.active_cache[day] = cached
        return cached

    def pick_product(self, day: date) -> Product:
        products, cum = self.active_products(day)
        return products[_pick_prefix(self.rng, cum, len(products))]

    def pick_variant(self, product: Product) -> Variant:
        variant_id = self.rng.choices(product.variant_ids, weights=product.variant_weights)[0]
        return self.variants[variant_id]

    # -- supply chain -------------------------------------------------------------------

    def build_supply(self) -> None:
        rng = self.rng
        inventory: list[Row] = []
        for variant in self.variants.values():
            product = variant.product
            stocked = [w for w in range(1, 7) if rng.random() < (0.9 if w <= 2 else 0.5)]
            for warehouse in stocked or [rng.randint(1, 6)]:
                scale = 20 * product.popularity * (1.6 if warehouse <= 2 else 0.8)
                quantity = int(rng.gammavariate(2.0, scale))
                if product.discontinued or rng.random() < 0.08:
                    quantity = rng.randint(0, 4)
                updated = END - timedelta(days=rng.uniform(0, 12))
                inventory.append((
                    len(inventory) + 1, variant.id, warehouse, quantity,
                    rng.choice((10, 15, 20, 25, 30, 40, 50)), _ts(updated),
                ))
        self.rows["inventory"] = inventory

        by_supplier: dict[int, list[Product]] = {}
        for product in self.products:
            by_supplier.setdefault(product.supplier_id, []).append(product)

        po_rows: list[Row] = []
        po_items: list[Row] = []
        for supplier_id, products in sorted(by_supplier.items()):
            lead = self.lead_times[supplier_id]
            day = START.date() - timedelta(days=rng.randint(20, 40))
            while True:
                day += timedelta(days=rng.randint(18, 40))
                if day > END.date():
                    break
                selling = [p for p in products if p.sells_on(day)]
                if not selling:
                    continue
                warehouse = rng.choices(range(1, 7), weights=(30, 30, 8, 12, 12, 8))[0]
                expected = day + timedelta(days=lead)
                actual = expected + timedelta(
                    days=rng.randint(4, 14) if rng.random() < 0.2 else rng.randint(-2, 2)
                )
                if rng.random() < 0.03:
                    status, received = "cancelled", None
                elif actual <= END.date():
                    status, received = "received", _d(actual)
                else:
                    status, received = "ordered", None
                po_id = len(po_rows) + 1
                po_rows.append(
                    (po_id, supplier_id, warehouse, status, _d(day), _d(expected), received)
                )
                chosen = rng.sample(selling, min(len(selling), rng.randint(2, 8)))
                for product in chosen:
                    variant = self.variants[rng.choice(product.variant_ids)]
                    quantity = max(10, int(round(product.popularity * rng.uniform(40, 160), -1)))
                    unit_cost = _money(
                        product.price_on(day) * product.cost_ratio * rng.uniform(0.95, 1.04)
                    )
                    po_items.append((len(po_items) + 1, po_id, variant.id, quantity, unit_cost))
        self.rows["purchase_orders"] = po_rows
        self.rows["purchase_order_items"] = po_items

    # -- marketing ----------------------------------------------------------------------

    def build_marketing(self) -> None:
        templates: list[tuple[str, str, tuple[int, int], tuple[int, int], float, int]] = [
            ("New Year Fitness", "email", (1, 2), (1, 31), 6000, 2023),
            ("Spring Refresh", "social", (3, 15), (4, 15), 9000, 2023),
            ("Creator Collab", "affiliate", (5, 1), (5, 31), 7000, 2024),
            ("Summer Outdoor", "paid_search", (6, 1), (7, 15), 12000, 2023),
            ("Back to School", "display", (8, 1), (9, 5), 8000, 2023),
            ("Loyalty Week", "email", (10, 7), (10, 14), 5000, 2025),
        ]
        campaigns: list[Campaign] = []
        for year in range(2023, END.year + 1):
            growth = 1 + 0.25 * (year - START.year)
            windows = [
                (f"{name} {year}", channel, date(year, *s), date(year, *e), budget)
                for name, channel, s, e, budget, first in templates
                if year >= first
            ]
            bf = _black_friday(year)
            windows += [
                (f"Black Friday {year}", "paid_search", bf - timedelta(days=5),
                 bf + timedelta(days=3), 30000),
                (f"Holiday Gift Guide {year}", "email", date(year, 12, 1), date(year, 12, 22),
                 14000),
            ]
            for name, channel, start, end, budget in sorted(windows, key=lambda w: w[2]):
                if start <= END.date():
                    campaigns.append(Campaign(len(campaigns) + 1, name, channel, start, end,
                                              round(budget * growth, -2)))
        self.campaigns = campaigns
        self.rows["marketing_campaigns"] = [
            (c.id, c.name, c.channel, _d(c.start), _d(c.end), c.budget) for c in campaigns
        ]

        far = date(2026, 12, 31)
        specs: list[tuple[str, str, int, float, bool, date, date]] = [
            ("WELCOME10", "10% off your first order", 10, 0, True, date(2023, 1, 1), far),
            ("SAVE15", "15% off orders over $120", 15, 120, True, date(2023, 1, 1), far),
            ("VIP20", "20% off for repeat customers", 20, 0, True, date(2023, 6, 1), far),
            ("LAUNCH5", "Launch week offer", 5, 0, False, date(2023, 1, 1), date(2023, 1, 31)),
        ]
        for year in range(2023, END.year + 1):
            bf = _black_friday(year)
            specs += [
                (f"SPRING{year}", "Spring sale", 10, 40, True, date(year, 3, 15),
                 date(year, 4, 15)),
                (f"SUMMER{year}", "Summer sale", 20, 60, True, date(year, 6, 1),
                 date(year, 7, 15)),
                (f"BF{year}", "Black Friday", 30 if year >= 2025 else 25, 50, True,
                 bf - timedelta(days=4), bf + timedelta(days=3)),
                (f"HOLIDAY{year}", "Holiday gifting", 15, 75, True, date(year, 12, 1),
                 date(year, 12, 24)),
            ]
        self.coupons = [
            Coupon(i, code, desc, pct, minimum, active, start, end)
            for i, (code, desc, pct, minimum, active, start, end) in enumerate(specs, 1)
        ]
        self.rows["coupons"] = [
            (c.id, c.code, c.description, c.percent_off, c.min_order_amount, int(c.active),
             _d(c.valid_from), _d(c.valid_to))
            for c in self.coupons
        ]
        self.coupon_by_code = {c.code: c for c in self.coupons}

    # -- customers ----------------------------------------------------------------------

    def build_customers(self) -> None:
        rng = self.rng
        span = (END - SIGNUP_START).days - 2
        days = [SIGNUP_START.date() + timedelta(days=i) for i in range(span)]
        weights = [
            (0.5 + 1.5 * i / span) * (1.4 if d.month in (11, 12) else 1.25 if d.month == 1 else 1)
            for i, d in enumerate(days)
        ]
        signups = sorted(
            datetime.combine(day, time(rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)))
            for day in rng.choices(days, weights=weights, k=N_CUSTOMERS)
        )
        countries = tuple((code, c.weight) for code, c in ref.COUNTRIES.items())
        states = tuple((s, s[1]) for s in ref.US_STATES)
        channels = (("organic", 34), ("paid_search", 22), ("social", 16), ("email", 8),
                    ("referral", 12), ("affiliate", 8))

        address_rows: list[Row] = []
        for index, created in enumerate(signups, start=1):
            first, last = rng.choice(ref.FIRST_NAMES), rng.choice(ref.LAST_NAMES)
            country = _weighted(rng, countries)
            info = ref.COUNTRIES[country]
            state: str | None = None
            if country == "US":
                state_info = _weighted(rng, states)
                state, city = state_info[0], rng.choice(state_info[2])
            else:
                city = rng.choice(info.cities)
            channel = _weighted(rng, channels)
            referred_by = rng.randint(1, index - 1) if channel == "referral" and index > 1 else None
            if channel == "referral" and referred_by is None:
                channel = "organic"
            segment = "business" if rng.random() < 0.12 else "consumer"
            propensity = 0.0 if rng.random() < 0.16 else min(rng.lognormvariate(0, 0.75), 5.0)
            local = f"{first}.{last}".lower().replace("'", "").replace(" ", "")
            email = f"{local}{index}@{rng.choice(ref.EMAIL_DOMAINS)}"
            customer = Customer(
                id=index, name=f"{first} {last}", email=email,
                phone=None if rng.random() < 0.08 else self._phone(country),
                country=country, state=state, city=city, segment=segment, channel=channel,
                referred_by=referred_by, opt_in=rng.random() < 0.55, created=created,
                propensity=propensity * (1.6 if segment == "business" else 1.0),
            )
            self.customers.append(customer)

            def add(kind: str, default: bool, cust: Customer = customer) -> int:
                address_id = len(address_rows) + 1
                address_rows.append((
                    address_id, cust.id, kind,
                    f"{rng.randint(1, 980)} {rng.choice(ref.COUNTRIES[cust.country].streets)}",
                    cust.city, cust.state, cust.country, self._postal(cust.country),
                    int(default),
                ))
                return address_id

            customer.shipping_address_id = add("shipping", True)
            customer.billing_address_id = (
                add("billing", True) if rng.random() < 0.45 else customer.shipping_address_id
            )
            if rng.random() < 0.2:
                add("shipping", False)
        self.rows["addresses"] = address_rows

    def _phone(self, country: str) -> str:
        r = self.rng
        if country in ("US", "CA"):
            return f"+1 {r.randint(201, 989)}-555-{r.randint(1000, 9999)}"
        if country == "GB":
            return f"+44 7700 9{r.randint(10000, 99999)}"
        if country == "DE":
            return f"+49 151 {r.randint(1000000, 9999999)}"
        if country == "FR":
            pairs = " ".join(str(r.randint(10, 99)) for _ in range(4))
            return f"+33 6 {pairs}"
        return f"+61 4{r.randint(10, 99)} {r.randint(100, 999)} {r.randint(100, 999)}"

    def _postal(self, country: str) -> str:
        r = self.rng
        letters = "ABCEGHJKLMNPRSTVXY"
        if country == "CA":
            return (f"{r.choice(letters)}{r.randint(1, 9)}{r.choice(letters)} "
                    f"{r.randint(1, 9)}{r.choice(letters)}{r.randint(1, 9)}")
        if country == "GB":
            return (f"{r.choice(('SW', 'M', 'B', 'EH', 'BS', 'LS'))}{r.randint(1, 20)} "
                    f"{r.randint(1, 9)}{r.choice(letters)}{r.choice(letters)}")
        if country == "AU":
            return str(r.randint(2000, 6999))
        return f"{r.randint(1000, 99999):05d}"

    # -- orders -------------------------------------------------------------------------

    def _order_times(self) -> list[datetime]:
        span = (END.date() - START.date()).days + 1
        days = [START.date() + timedelta(days=i) for i in range(span)]
        # Demand scales with the customer base (so launch months aren't shared by a handful of
        # early signups), then with season, weekday and promotions.
        signed_up = [datetime.combine(c.created.date(), time()) for c in self.customers]
        weights = []
        for day in days:
            base = bisect.bisect_right(signed_up, datetime.combine(day, time())) or 1
            weight = base**0.85 * _MONTH_FACTOR[day.month - 1]
            weight *= _WEEKDAY_FACTOR[day.weekday()]
            offset = (day - _black_friday(day.year)).days
            weight *= {0: 4.0, 1: 2.2, 2: 2.2, 3: 3.0}.get(offset, 1.4 if -4 <= offset < 0 else 1)
            if day.month == 12 and day.day in (24, 25, 26):
                weight *= 0.35 if day.day == 25 else 0.6
            if day.month == 7 and 9 <= day.day <= 11:
                weight *= 1.7
            weights.append(weight)
        self.day_weights = (days, weights)
        hours = list(range(24))
        return sorted(
            datetime.combine(day, time(self.rng.choices(hours, weights=_HOUR_WEIGHTS)[0],
                                       self.rng.randint(0, 59), self.rng.randint(0, 59)))
            for day in self.rng.choices(days, weights=weights, k=N_ORDERS)
        )

    def build_orders(self) -> None:
        rng = self.rng
        buyers = [c for c in self.customers if c.propensity > 0]
        cum: list[float] = []
        total = 0.0
        for buyer in buyers:
            total += buyer.propensity
            cum.append(total)
        eligible = 0
        waiting: list[Customer] = []  # signed up, yet to place a first order

        self.order_rows: list[Row] = []
        self.item_rows: list[Row] = []
        self.history_rows: list[tuple[int, str, str]] = []
        self.payment_rows: list[Row] = []
        self.shipment_rows: list[Row] = []
        self.coupon_rows: list[tuple[int, int]] = []
        self.returns: list[ReturnCase] = []
        self.review_rows: list[Row] = []
        self.converted_carts: list[tuple[Customer, datetime, int, list[Line]]] = []

        for order_id, placed in enumerate(self._order_times(), start=1):
            while eligible < len(buyers) and buyers[eligible].created < placed:
                waiting.append(buyers[eligible])
                eligible += 1
            waiting = [c for c in waiting if c.order_count == 0
                       and (placed - c.created).days < 75]
            if eligible == 0:
                continue  # nobody has signed up yet
            if waiting and rng.random() < 0.3:
                customer = waiting.pop(rng.randrange(len(waiting)))
            else:
                customer = buyers[_pick_prefix(rng, cum, eligible)]
            self._simulate_order(order_id, customer, placed)
            customer.order_count += 1

    def _simulate_order(self, order_id: int, customer: Customer, placed: datetime) -> None:
        rng = self.rng
        day = placed.date()
        info = ref.COUNTRIES[customer.country]
        currency = info.currency
        fx = self.fx[(currency, _month(day))]

        progress = (placed - START) / (END - START)
        mobile = 0.22 + 0.2 * progress
        channel = _weighted(rng, (
            ("web", 1 - mobile - 0.12), ("mobile_app", mobile), ("marketplace", 0.08),
            ("phone", 0.1 if customer.segment == "business" else 0.04),
        ))

        lines: list[Line] = []
        seen: dict[int, Line] = {}
        for _ in range(_weighted(rng, ((1, 42), (2, 28), (3, 16), (4, 9), (5, 5)))):
            product = self.pick_product(day)
            variant = self.pick_variant(product)
            quantity = _weighted(rng, ((1, 78), (2, 15), (3, 5), (4, 2)))
            if customer.segment == "business" and rng.random() < 0.25:
                quantity += rng.randint(2, 8)
            if variant.id in seen:
                seen[variant.id].quantity += quantity
                continue
            usd = product.price_on(day) * variant.multiplier
            discount = 0.0
            if _in_sale(day) and rng.random() < 0.5:
                discount = rng.choice((0.1, 0.15, 0.2, 0.25))
            elif rng.random() < 0.07:
                discount = rng.choice((0.05, 0.1, 0.15))
            line = Line(len(self.item_rows) + len(lines) + 1, variant, quantity,
                        _money(usd / fx), discount)
            seen[variant.id] = line
            lines.append(line)

        subtotal = _money(sum(line.net for line in lines))
        subtotal_usd = subtotal * fx
        coupon = self._choose_coupon(customer, day, subtotal_usd)
        discount_total = _money(subtotal * coupon.percent_off / 100) if coupon else 0.0
        express = rng.random() < (0.2 if customer.segment == "business" else 0.1)
        fee_usd = 14.99 if express else (
            0.0 if subtotal_usd >= 75 or channel == "marketplace" else 5.99
        )
        shipping_fee = _money(fee_usd / fx)
        tax_rate = info.tax_rate
        if customer.country == "US":
            tax_rate = next(s[3] for s in ref.US_STATES if s[0] == customer.state)
        tax_total = _money((subtotal - discount_total) * tax_rate)
        order_total = _money(subtotal - discount_total + shipping_fee + tax_total)

        active = [c for c in self.campaigns if c.start <= day <= c.end]
        campaign_id = None
        if active:
            campaign = rng.choice(active)
            chance = 0.45 if campaign.channel == customer.channel else 0.22
            campaign_id = campaign.id if rng.random() < chance else None

        status = self._fulfil(order_id, customer, placed, lines, order_total, tax_rate,
                              coupon.percent_off if coupon else 0, express, fx)

        self.order_rows.append((
            order_id, customer.id, status, channel, _ts(placed), currency, subtotal,
            discount_total, shipping_fee, tax_total, order_total, customer.shipping_address_id,
            customer.billing_address_id, campaign_id,
        ))
        for line in lines:
            self.item_rows.append((line.id, order_id, line.variant.id, line.quantity,
                                   line.unit_price, line.discount))
        if coupon:
            self.coupon_rows.append((order_id, coupon.id))
        if channel in ("web", "mobile_app"):
            self.converted_carts.append((customer, placed, order_id, lines))

    def _choose_coupon(self, customer: Customer, day: date, subtotal_usd: float) -> Coupon | None:
        rng = self.rng
        welcome, vip, save = (self.coupon_by_code[c] for c in ("WELCOME10", "VIP20", "SAVE15"))
        if customer.order_count == 0 and welcome.valid_on(day) and rng.random() < 0.45:
            return welcome
        if customer.order_count >= 4 and vip.valid_on(day) and rng.random() < 0.12:
            return vip
        seasonal = [
            c for c in self.coupons
            if c.code not in ("WELCOME10", "VIP20", "SAVE15")
            and c.valid_on(day) and subtotal_usd >= c.min_order_amount
        ]
        if seasonal and rng.random() < 0.3:
            return seasonal[0]
        if subtotal_usd >= save.min_order_amount and rng.random() < 0.06:
            return save
        return None

    def _fulfil(
        self,
        order_id: int,
        customer: Customer,
        placed: datetime,
        lines: list[Line],
        total: float,
        tax_rate: float,
        coupon_pct: int,
        express: bool,
        fx: float,
    ) -> str:
        """Play out payment, shipping, delivery and returns; return the order's current status."""
        rng = self.rng
        history = self.history_rows
        history.append((order_id, "pending", _ts(placed)))
        method = _weighted(rng, _PAY_METHODS)
        provider = "paypal" if method == "paypal" else (
            "adyen" if method == "bank_transfer" or rng.random() < 0.3 else "stripe"
        )

        def pay(amount: float, status: str, at: datetime) -> None:
            fee = 0.0
            if status == "captured":
                rate, fixed = {"paypal": (0.0349, 0.49), "bank_transfer": (0.005, 0.0),
                               "gift_card": (0.0, 0.0)}.get(method, (0.029, 0.30))
                fee = _money(amount * rate + fixed / fx)
            self.payment_rows.append((order_id, method, provider, amount, fee, status, _ts(at)))

        if END - placed < timedelta(hours=6) and rng.random() < 0.6:
            return "pending"

        roll = rng.random()
        if roll < 0.02:  # card declined and never retried
            failed_at = placed + timedelta(minutes=rng.randint(1, 5))
            pay(total, "failed", failed_at)
            self._maybe_ticket(0.3, customer, order_id, "payment_issue",
                               failed_at + timedelta(minutes=rng.randint(5, 120)))
            cancelled = failed_at + timedelta(hours=rng.uniform(1, 24))
            if cancelled > END:
                return "pending"
            history.append((order_id, "cancelled", _ts(cancelled)))
            return "cancelled"

        paid_at = placed + timedelta(minutes=rng.randint(1, 10))
        if rng.random() < 0.05:  # first attempt declined, retry succeeded
            failed_at = placed + timedelta(minutes=rng.randint(1, 3))
            pay(total, "failed", failed_at)
            paid_at = failed_at + timedelta(minutes=rng.randint(2, 15))
            self._maybe_ticket(0.3, customer, order_id, "payment_issue",
                               failed_at + timedelta(minutes=rng.randint(5, 60)))
        if paid_at > END:
            return "pending"
        pay(total, "captured", paid_at)
        history.append((order_id, "paid", _ts(paid_at)))
        customer.lifetime_usd += total * fx

        if roll < 0.045:  # customer cancelled before dispatch
            cancelled = paid_at + timedelta(hours=rng.uniform(1, 20))
            if cancelled <= END:
                pay(total, "refunded", cancelled + timedelta(minutes=rng.randint(5, 90)))
                history.append((order_id, "cancelled", _ts(cancelled)))
                customer.lifetime_usd -= total * fx
                return "cancelled"

        handling = timedelta(hours=rng.uniform(4, 40))
        if _is_peak(paid_at.date()):
            handling += timedelta(hours=rng.uniform(12, 48))
        first_ship = paid_at + handling
        if first_ship > END:
            return "paid"

        groups = [lines]
        if len(lines) >= 4 and rng.random() < 0.35:
            cut = rng.randint(1, len(lines) - 1)
            groups = [lines[:cut], lines[cut:]]

        info = ref.COUNTRIES[customer.country]
        if customer.country == "US":
            west = next(s[4] for s in ref.US_STATES if s[0] == customer.state)
            warehouse = 1 if west else 2
        else:
            warehouse = info.warehouse
        carrier = _weighted(rng, info.carriers)
        promised_days = 2 if express else info.promised_days

        shipped_lines: list[Line] = []
        deliveries: list[datetime | None] = []
        late = False
        for n, group in enumerate(groups):
            shipped_at = first_ship + timedelta(days=rng.uniform(1, 3) if n else 0)
            if shipped_at > END:
                continue
            promised = datetime.combine(
                shipped_at.date() + timedelta(days=promised_days), time(23, 59, 59)
            )
            late_rate = ref.CARRIER_LATE_RATE[carrier] * (1.8 if _is_peak(shipped_at.date())
                                                          else 1.0) * (0.6 if express else 1.0)
            is_late = rng.random() < late_rate
            transit = promised_days + rng.randint(1, 4) if is_late else rng.randint(
                max(1, promised_days - 2), promised_days)
            arrival = datetime.combine(
                shipped_at.date() + timedelta(days=transit),
                time(rng.randint(9, 20), rng.randint(0, 59)),
            )
            delivered: datetime | None = arrival
            if arrival > END:
                delivered = None
                if promised < END:
                    self._maybe_ticket(0.5, customer, order_id, "shipping_delay",
                                       promised + timedelta(hours=rng.uniform(2, 30)))
            elif is_late:
                late = True
                self._maybe_ticket(0.3, customer, order_id, "shipping_delay",
                                   promised + timedelta(hours=rng.uniform(2, 30)))
            weight = sum(line.quantity * line.variant.product.weight_kg for line in group)
            cost = (15.0 if express else 6.5) + 0.85 * weight
            cost += 0 if customer.country == "US" else 2.5
            self.shipment_rows.append((
                order_id, warehouse, carrier, "express" if express else "standard",
                f"{carrier[:2].upper()}{order_id:07d}{n + 1}",
                "delivered" if delivered else "in_transit", _money(cost), _ts(shipped_at),
                _ts(promised), _ts(delivered) if delivered else None,
            ))
            shipped_lines += group
            deliveries.append(delivered)

        history.append((order_id, "shipped", _ts(first_ship)))
        if len(shipped_lines) < len(lines) or any(d is None for d in deliveries):
            return "shipped"
        delivered_at = max(d for d in deliveries if d is not None)
        history.append((order_id, "delivered", _ts(delivered_at)))

        status = self._maybe_return(order_id, customer, lines, delivered_at, late, tax_rate,
                                    coupon_pct, pay, fx)
        self._maybe_review(order_id, customer, lines, delivered_at, late)
        return status

    def _maybe_return(
        self,
        order_id: int,
        customer: Customer,
        lines: list[Line],
        delivered_at: datetime,
        late: bool,
        tax_rate: float,
        coupon_pct: int,
        pay: _PayFn,
        fx: float,
    ) -> str:
        rng = self.rng
        returned: list[tuple[Line, int]] = []
        for line in lines:
            product = line.variant.product
            chance = product.leaf.return_rate * (1.6 - product.quality) * (1.25 if late else 1)
            if rng.random() < chance:
                quantity = line.quantity
                if quantity > 1 and rng.random() < 0.3:
                    quantity = rng.randint(1, quantity - 1)
                returned.append((line, quantity))
        if not returned:
            return "delivered"

        requested = delivered_at + timedelta(days=rng.uniform(1, 28))
        if requested > END:
            return "delivered"
        kind = returned[0][0].variant.product.leaf.variant_kind
        reason = _weighted(rng, _APPAREL_REASONS if kind in ("apparel", "shoes")
                           else _GOODS_REASONS)
        if late and rng.random() < 0.3:
            reason = "late_delivery"

        items = []
        for line, quantity in returned:
            if reason in ("damaged_in_transit", "defective") and rng.random() < 0.7:
                condition = "damaged"
            else:
                condition = "unopened" if rng.random() < 0.5 else "opened"
            items.append((line.id, quantity, condition))

        status, resolved, refund = "requested", None, None
        if rng.random() < 0.07:
            rejected = requested + timedelta(days=rng.uniform(2, 6))
            if rejected <= END:
                status, resolved = "rejected", rejected
        else:
            done = requested + timedelta(days=rng.uniform(4, 16))
            if done <= END:
                status, resolved = "refunded", done
                gross = sum(q * line.unit_price * (1 - line.discount) for line, q in returned)
                refund = _money(gross * (1 - coupon_pct / 100) * (1 + tax_rate))
            elif requested + timedelta(days=2) <= END:
                status = "approved"
        self.returns.append(ReturnCase(order_id, status, reason, requested, resolved, refund,
                                       items))

        self.returned_lines.update(line.id for line, _ in returned)
        if reason in ("damaged_in_transit", "defective"):
            self._maybe_ticket(0.45, customer, order_id, "damaged_item",
                               delivered_at + timedelta(hours=rng.uniform(2, 72)))
        elif rng.random() < 0.15:
            self._maybe_ticket(1.0, customer, order_id, "return_request",
                               max(delivered_at, requested - timedelta(hours=rng.uniform(1, 48))))

        if status == "refunded" and resolved is not None and refund is not None:
            pay(refund, "refunded", resolved + timedelta(hours=rng.uniform(1, 30)))
            customer.lifetime_usd -= refund * fx
            if all(q == line.quantity for line, q in returned) and len(returned) == len(lines):
                self.history_rows.append((order_id, "refunded", _ts(resolved)))
                return "refunded"
        return "delivered"

    def _maybe_review(
        self, order_id: int, customer: Customer, lines: list[Line], delivered_at: datetime,
        late: bool,
    ) -> None:
        rng = self.rng
        for line in lines:
            product = line.variant.product
            key = (customer.id, product.id)
            if key in self.reviewed:
                continue
            was_returned = line.id in self.returned_lines
            chance = 0.35 if was_returned else (0.14 if product.leaf.variant_kind == "tech"
                                                else 0.09)
            if rng.random() >= chance:
                continue
            created = delivered_at + timedelta(days=rng.uniform(2, 30))
            if created > END:
                continue
            if was_returned:
                rating = rng.choice((1, 1, 2, 2, 3))
            else:
                score = product.quality * 5.3 - 0.4 + rng.gauss(0, 0.85) - (1.2 if late else 0)
                rating = min(5, max(1, round(score)))
            self.reviewed.add(key)
            self.review_rows.append(self._review(product.id, customer.id, order_id, rating, True,
                                                 created))

    def _review(
        self, product_id: int, customer_id: int, order_id: int | None, rating: int,
        verified: bool, created: datetime,
    ) -> Row:
        rng = self.rng
        votes = int(rng.expovariate(1 / (3.0 if rating in (1, 5) else 1.5)))
        return (product_id, customer_id, order_id, rating, rng.choice(ref.REVIEW_TITLES[rating]),
                rng.choice(ref.REVIEW_BODIES[rating]), int(verified), votes, _ts(created))

    def _maybe_ticket(
        self, chance: float, customer: Customer, order_id: int | None, category: str,
        created: datetime,
    ) -> None:
        if created <= END and self.rng.random() < chance:
            self.tickets.append(TicketSeed(customer.id, order_id, category, created))

    # -- behaviour: carts, wishlists, extra reviews, support --------------------------

    def build_behaviour(self) -> None:
        rng = self.rng
        carts: list[tuple[int, str, datetime, datetime, int | None, list[tuple[int, int]]]] = []
        for customer, placed, order_id, lines in self.converted_carts:
            created = max(placed - timedelta(minutes=rng.uniform(3, 150)),
                          customer.created + timedelta(minutes=1))
            carts.append((customer.id, "converted", created, placed, order_id,
                          [(line.variant.id, line.quantity) for line in lines]))

        cum: list[float] = []
        total = 0.0
        for customer in self.customers:
            total += customer.propensity + 0.5
            cum.append(total)
        days, weights = self.day_weights
        signed_up = [c.created for c in self.customers]
        for day in rng.choices(days, weights=weights, k=N_ABANDONED_CARTS):
            created = datetime.combine(day, time(rng.choices(range(24), weights=_HOUR_WEIGHTS)[0],
                                                 rng.randint(0, 59), rng.randint(0, 59)))
            eligible = bisect.bisect_left(signed_up, created)
            if eligible == 0 or created > END:
                continue
            customer = self.customers[_pick_prefix(rng, cum, eligible)]
            updated = created + timedelta(minutes=rng.uniform(1, 90))
            status = "active" if updated > END - timedelta(days=3) else "abandoned"
            items = []
            for _ in range(_weighted(rng, ((1, 50), (2, 28), (3, 14), (4, 8)))):
                variant = self.pick_variant(self.pick_product(day))
                items.append((variant.id, rng.choice((1, 1, 1, 2))))
            carts.append((customer.id, status, created, min(updated, END), None, items))

        carts.sort(key=lambda cart: cart[2])
        cart_rows: list[Row] = []
        cart_items: list[Row] = []
        for cart_id, (customer_id, status, created, updated, cart_order, items) in enumerate(
            carts, start=1
        ):
            cart_rows.append((cart_id, customer_id, status, _ts(created), _ts(updated), cart_order))
            step = (updated - created) / (len(items) + 1)
            for n, (variant_id, quantity) in enumerate(items, start=1):
                cart_items.append((len(cart_items) + 1, cart_id, variant_id, quantity,
                                   _ts(created + step * n)))
        self.rows["carts"] = cart_rows
        self.rows["cart_items"] = cart_items

        wishlist: dict[tuple[int, int], datetime] = {}
        weights_by_product = [p.popularity for p in self.products]
        for _ in range(N_WISHLIST_ATTEMPTS):
            customer = rng.choice(self.customers)
            product = rng.choices(self.products, weights=weights_by_product)[0]
            start = max(customer.created, datetime.combine(product.created, time(9)))
            if start >= END or (customer.id, product.id) in wishlist:
                continue
            wishlist[(customer.id, product.id)] = start + (END - start) * rng.random()
        self.rows["wishlist_items"] = sorted(
            ((c, p, _ts(added)) for (c, p), added in wishlist.items()), key=lambda r: str(r[2])
        )

        for _ in range(N_UNVERIFIED_REVIEWS):
            customer = rng.choice(self.customers)
            product = rng.choice(self.products)
            start = max(customer.created, datetime.combine(product.created, time(9)))
            if start >= END or (customer.id, product.id) in self.reviewed:
                continue
            self.reviewed.add((customer.id, product.id))
            rating = min(5, max(1, round(product.quality * 5 + rng.gauss(0, 1.4))))
            self.review_rows.append(self._review(product.id, customer.id, None, rating, False,
                                                 start + (END - start) * rng.random()))
        self.review_rows.sort(key=lambda r: str(r[8]))
        self.rows["reviews"] = [(i, *row) for i, row in enumerate(self.review_rows, start=1)]

        for _ in range(N_GENERAL_TICKETS):
            customer = rng.choice(self.customers)
            created = customer.created + (END - customer.created) * rng.random()
            category = "product_question" if rng.random() < 0.6 else "account"
            self.tickets.append(TicketSeed(customer.id, None, category, created))
        self._build_tickets()

    def _build_tickets(self) -> None:
        rng = self.rng
        segments = {c.id: c.segment for c in self.customers}
        rows: list[Row] = []
        for seed in sorted(self.tickets, key=lambda t: t.created_at):
            priority = _weighted(rng, _TICKET_PRIORITY[seed.category])
            if segments[seed.customer_id] == "business" and rng.random() < 0.5:
                priority = _PRIORITY_ORDER[min(_PRIORITY_ORDER.index(priority) + 1, 3)]
            channel = _weighted(rng, (("chat", 45), ("email", 40), ("phone", 15)))
            if channel == "chat":
                wait = timedelta(minutes=rng.uniform(1, 25))
            elif channel == "phone":
                wait = timedelta(minutes=rng.uniform(0, 6))
            else:
                wait = timedelta(hours=rng.uniform(1, 30))
                if seed.created_at.weekday() >= 5:
                    wait *= 1.8
            if priority == "urgent":
                wait *= 0.4
            first_response: datetime | None = seed.created_at + wait
            low, high = _TICKET_RESOLVE_DAYS[seed.category]
            resolve_days = rng.uniform(low, high)
            resolved: datetime | None = seed.created_at + timedelta(days=resolve_days)
            satisfaction = None
            if first_response is not None and first_response > END:
                status, first_response, resolved = "open", None, None
            elif resolved is not None and resolved > END:
                status, resolved = "pending", None
            else:
                old = resolved is not None and END - resolved > timedelta(days=7)
                status = "closed" if old and rng.random() < 0.85 else "resolved"
                if rng.random() >= 0.45:
                    score = 5.2 - 0.45 * resolve_days + rng.gauss(0, 0.8)
                    score -= 0.8 if seed.category == "damaged_item" else 0
                    satisfaction = min(5, max(1, round(score)))
            rows.append((
                len(rows) + 1, seed.customer_id, seed.order_id, seed.category, priority, channel,
                status, _ts(seed.created_at), _ts(first_response) if first_response else None,
                _ts(resolved) if resolved else None, satisfaction,
            ))
        self.rows["support_tickets"] = rows

    # -- finalise -------------------------------------------------------------------------

    def finalise(self) -> None:
        def tier(spend: float) -> str:
            if spend >= 5000:
                return "platinum"
            if spend >= 2000:
                return "gold"
            return "silver" if spend >= 500 else "bronze"

        self.rows["customers"] = [
            (c.id, c.name, c.email, c.phone, c.country, c.segment, tier(c.lifetime_usd), c.channel,
             c.referred_by, int(c.opt_in), _ts(c.created))
            for c in self.customers
        ]
        self.rows["orders"] = self.order_rows
        self.rows["order_items"] = self.item_rows
        self.rows["order_coupons"] = self.coupon_rows
        self.rows["order_status_history"] = [
            (i, *row) for i, row in enumerate(sorted(self.history_rows, key=lambda r: r[2]), 1)
        ]
        payments = sorted(self.payment_rows, key=lambda r: str(r[6]))
        self.rows["payments"] = [(i, *row) for i, row in enumerate(payments, 1)]
        shipments = sorted(self.shipment_rows, key=lambda r: str(r[7]))
        self.rows["shipments"] = [(i, *row) for i, row in enumerate(shipments, 1)]
        return_rows: list[Row] = []
        return_items: list[Row] = []
        for return_id, case in enumerate(sorted(self.returns, key=lambda r: r.requested_at), 1):
            return_rows.append((
                return_id, case.order_id, case.status, case.reason, _ts(case.requested_at),
                _ts(case.resolved_at) if case.resolved_at else None, case.refund_amount,
            ))
            for order_item_id, quantity, condition in case.items:
                return_items.append(
                    (len(return_items) + 1, return_id, order_item_id, quantity, condition)
                )
        self.rows["returns"] = return_rows
        self.rows["return_items"] = return_items


# Parent-first insert order (foreign keys are enforced on insert).
_INSERTS: list[tuple[str, str]] = [
    ("categories", "id, name, parent_id, created_at"),
    ("brands", "id, name, country, founded_year"),
    ("suppliers", "id, name, country, email, lead_time_days, rating, created_at"),
    ("products", "id, sku, name, category_id, brand_id, supplier_id, price, cost, weight_kg, "
                 "is_active, created_at, discontinued_at"),
    ("product_price_history", "id, product_id, price, valid_from, valid_to"),
    ("product_variants", "id, product_id, sku, color, size, price, created_at"),
    ("warehouses", "id, name, city, country"),
    ("inventory", "id, variant_id, warehouse_id, quantity, reorder_point, updated_at"),
    ("purchase_orders", "id, supplier_id, warehouse_id, status, ordered_at, expected_at, "
                        "received_at"),
    ("purchase_order_items", "id, purchase_order_id, variant_id, quantity, unit_cost"),
    ("marketing_campaigns", "id, name, channel, start_date, end_date, budget"),
    ("customers", "id, name, email, phone, country, segment, loyalty_tier, acquisition_channel, "
                  "referred_by_id, marketing_opt_in, created_at"),
    ("addresses", "id, customer_id, type, line1, city, state, country, postal_code, is_default"),
    ("coupons", "id, code, description, percent_off, min_order_amount, active, valid_from, "
                "valid_to"),
    ("orders", "id, customer_id, status, channel, placed_at, currency, subtotal, discount_total, "
               "shipping_fee, tax_total, total, shipping_address_id, billing_address_id, "
               "campaign_id"),
    ("order_items", "id, order_id, variant_id, quantity, unit_price, discount"),
    ("order_status_history", "id, order_id, status, changed_at"),
    ("order_coupons", "order_id, coupon_id"),
    ("payments", "id, order_id, method, provider, amount, fee, status, paid_at"),
    ("shipments", "id, order_id, warehouse_id, carrier, service_level, tracking_number, status, "
                  "shipping_cost, shipped_at, promised_at, delivered_at"),
    ("returns", "id, order_id, status, reason, requested_at, resolved_at, refund_amount"),
    ("return_items", "id, return_id, order_item_id, quantity, condition"),
    ("carts", "id, customer_id, status, created_at, updated_at, order_id"),
    ("cart_items", "id, cart_id, variant_id, quantity, added_at"),
    ("wishlist_items", "customer_id, product_id, added_at"),
    ("reviews", "id, product_id, customer_id, order_id, rating, title, body, "
                "is_verified_purchase, helpful_votes, created_at"),
    ("support_tickets", "id, customer_id, order_id, category, priority, channel, status, "
                        "created_at, first_response_at, resolved_at, satisfaction_score"),
    ("exchange_rates", "currency, rate_date, rate_to_usd"),
]


def generate() -> dict[str, Sequence[Row]]:
    """Run the simulation and return rows per table (no database needed)."""
    world = _World()
    world.build_reference()
    world.build_catalogue()
    world.build_supply()
    world.build_marketing()
    world.build_customers()
    world.build_orders()
    world.build_behaviour()
    world.finalise()
    return world.rows


def seed_database(conn: sqlite3.Connection) -> None:
    rows = generate()
    for table, columns in _INSERTS:
        placeholders = ", ".join("?" for _ in columns.split(","))
        conn.executemany(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", rows[table]
        )
    conn.commit()
