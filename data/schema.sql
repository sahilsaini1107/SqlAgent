-- SQL Agent — sample e-commerce schema (synthetic; stands in for a provided schema).
--
-- Models a mid-size international online retailer: a three-level catalogue with brands,
-- price history, variants and multi-warehouse stock; supplier purchase orders; customers
-- with addresses, carts, wishlists and loyalty tiers; orders with a status timeline,
-- payments, shipments, returns and coupons; marketing campaigns; and customer support.
--
-- Conventions (also repeated in the column comments, which the agent sees):
-- * Timestamps are ISO-8601 TEXT 'YYYY-MM-DD HH:MM:SS' (UTC); dates are 'YYYY-MM-DD'.
-- * Booleans are INTEGER 0/1.
-- * Catalogue prices and costs are USD. Order money is in orders.currency; convert to USD
--   with exchange_rates (monthly rate keyed by the first day of the month).
-- * Line net amount = quantity * unit_price * (1 - discount).
--
-- Comments inside a CREATE TABLE are stored by SQLite and surfaced to the agent: the comment
-- on the CREATE line describes the table, a comment after a column describes that column.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------------------
-- Catalogue
-- ---------------------------------------------------------------------------------------

CREATE TABLE categories (  -- Product taxonomy, up to three levels (department > group > leaf)
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    parent_id  INTEGER REFERENCES categories(id),  -- NULL for top-level departments
    created_at TEXT NOT NULL
);

CREATE TABLE brands (  -- Manufacturer or label a product is sold under
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    country      TEXT NOT NULL,  -- ISO 3166 alpha-2 country of origin
    founded_year INTEGER
);

CREATE TABLE suppliers (  -- Vendors stock is purchased from
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    country        TEXT NOT NULL,  -- ISO 3166 alpha-2
    email          TEXT,
    lead_time_days INTEGER NOT NULL,  -- quoted days from purchase order to delivery
    rating         REAL,  -- internal vendor score 1.0-5.0
    created_at     TEXT NOT NULL
);

CREATE TABLE products (  -- Catalogue item; customers buy one of its variants
    id              INTEGER PRIMARY KEY,
    sku             TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    category_id     INTEGER NOT NULL REFERENCES categories(id),  -- always a leaf category
    brand_id        INTEGER NOT NULL REFERENCES brands(id),
    supplier_id     INTEGER REFERENCES suppliers(id),
    price           REAL NOT NULL,  -- current list price in USD (past prices in product_price_history)
    cost            REAL NOT NULL,  -- current unit cost in USD, for margin analysis
    weight_kg       REAL,
    is_active       INTEGER NOT NULL DEFAULT 1,  -- 0/1; 0 means discontinued
    created_at      TEXT NOT NULL,  -- date the product was listed
    discontinued_at TEXT  -- date it stopped selling; NULL while active
);

CREATE TABLE product_price_history (  -- List-price windows per product; the open row (valid_to NULL) is the current price
    id         INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    price      REAL NOT NULL,  -- USD list price during the window
    valid_from TEXT NOT NULL,  -- inclusive date
    valid_to   TEXT  -- exclusive date; NULL for the current price
);

CREATE TABLE product_variants (  -- Purchasable SKU of a product (colour, size, format)
    id         INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    sku        TEXT NOT NULL UNIQUE,
    color      TEXT,
    size       TEXT,  -- clothing size, shoe size (US), or book format
    price      REAL NOT NULL,  -- current USD price of this variant
    created_at TEXT NOT NULL
);

-- ---------------------------------------------------------------------------------------
-- Supply chain
-- ---------------------------------------------------------------------------------------

CREATE TABLE warehouses (  -- Fulfilment centres orders ship from
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    city    TEXT NOT NULL,
    country TEXT NOT NULL  -- ISO 3166 alpha-2
);

CREATE TABLE inventory (  -- Current stock of each variant at each warehouse
    id            INTEGER PRIMARY KEY,
    variant_id    INTEGER NOT NULL REFERENCES product_variants(id),
    warehouse_id  INTEGER NOT NULL REFERENCES warehouses(id),
    quantity      INTEGER NOT NULL,  -- units on hand now
    reorder_point INTEGER NOT NULL,  -- restock when quantity is at or below this
    updated_at    TEXT NOT NULL,
    UNIQUE (variant_id, warehouse_id)
);

CREATE TABLE purchase_orders (  -- Replenishment orders placed with suppliers
    id           INTEGER PRIMARY KEY,
    supplier_id  INTEGER NOT NULL REFERENCES suppliers(id),
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),  -- receiving warehouse
    status       TEXT NOT NULL,  -- ordered|received|cancelled
    ordered_at   TEXT NOT NULL,  -- date
    expected_at  TEXT NOT NULL,  -- date promised by the supplier
    received_at  TEXT  -- date received; NULL unless status = 'received'
);

CREATE TABLE purchase_order_items (  -- Lines of a purchase order
    id                INTEGER PRIMARY KEY,
    purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
    variant_id        INTEGER NOT NULL REFERENCES product_variants(id),
    quantity          INTEGER NOT NULL,
    unit_cost         REAL NOT NULL  -- USD paid per unit
);

-- ---------------------------------------------------------------------------------------
-- Customers and marketing
-- ---------------------------------------------------------------------------------------

CREATE TABLE marketing_campaigns (  -- Promotions that orders can be attributed to
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    channel    TEXT NOT NULL,  -- paid_search|social|email|affiliate|display
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,  -- inclusive
    budget     REAL NOT NULL  -- total spend in USD
);

CREATE TABLE customers (  -- Registered shoppers
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    email               TEXT NOT NULL UNIQUE,
    phone               TEXT,
    country             TEXT NOT NULL,  -- ISO 3166 alpha-2 home country: US|CA|GB|DE|FR|AU
    segment             TEXT NOT NULL,  -- consumer|business
    loyalty_tier        TEXT NOT NULL,  -- bronze|silver|gold|platinum by lifetime net spend in USD: <500, <2000, <5000, >=5000
    acquisition_channel TEXT NOT NULL,  -- organic|paid_search|social|email|referral|affiliate
    referred_by_id      INTEGER REFERENCES customers(id),  -- referring customer when acquisition_channel = 'referral'
    marketing_opt_in    INTEGER NOT NULL DEFAULT 0,  -- 0/1
    created_at          TEXT NOT NULL  -- signup timestamp
);

CREATE TABLE addresses (  -- Customer shipping and billing addresses
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    type        TEXT NOT NULL,  -- shipping|billing
    line1       TEXT NOT NULL,
    city        TEXT NOT NULL,
    state       TEXT,  -- US state code; NULL outside the US
    country     TEXT NOT NULL,  -- ISO 3166 alpha-2
    postal_code TEXT,
    is_default  INTEGER NOT NULL DEFAULT 1  -- 0/1
);

CREATE TABLE coupons (  -- Order-level discount codes
    id               INTEGER PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    description      TEXT,
    percent_off      INTEGER NOT NULL,  -- 0..100, applied to the order subtotal
    min_order_amount REAL NOT NULL DEFAULT 0,  -- minimum subtotal in USD
    active           INTEGER NOT NULL DEFAULT 1,  -- 0/1
    valid_from       TEXT,  -- date
    valid_to         TEXT  -- inclusive date
);

-- ---------------------------------------------------------------------------------------
-- Orders
-- ---------------------------------------------------------------------------------------

CREATE TABLE orders (  -- Customer checkouts; all money columns are in orders.currency
    id                  INTEGER PRIMARY KEY,
    customer_id         INTEGER NOT NULL REFERENCES customers(id),
    status              TEXT NOT NULL,  -- current status: pending|paid|shipped|delivered|cancelled|refunded (refunded = fully returned)
    channel             TEXT NOT NULL,  -- web|mobile_app|marketplace|phone
    placed_at           TEXT NOT NULL,  -- checkout timestamp
    currency            TEXT NOT NULL DEFAULT 'USD',  -- USD|EUR|GBP|CAD|AUD; to get USD multiply by exchange_rates.rate_to_usd for strftime('%Y-%m-01', placed_at)
    subtotal            REAL NOT NULL,  -- sum of line net amounts
    discount_total      REAL NOT NULL DEFAULT 0,  -- coupon discount on the subtotal
    shipping_fee        REAL NOT NULL DEFAULT 0,  -- shipping charged to the customer
    tax_total           REAL NOT NULL DEFAULT 0,
    total               REAL NOT NULL,  -- amount charged = subtotal - discount_total + shipping_fee + tax_total
    shipping_address_id INTEGER REFERENCES addresses(id),
    billing_address_id  INTEGER REFERENCES addresses(id),
    campaign_id         INTEGER REFERENCES marketing_campaigns(id)  -- attributed campaign; NULL if none
);

CREATE TABLE order_items (  -- Order lines; line net = quantity * unit_price * (1 - discount)
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    variant_id INTEGER NOT NULL REFERENCES product_variants(id),
    quantity   INTEGER NOT NULL,
    unit_price REAL NOT NULL,  -- price per unit at purchase time, in orders.currency
    discount   REAL NOT NULL DEFAULT 0  -- fractional line discount 0..1 (sale pricing)
);

CREATE TABLE order_status_history (  -- Every status an order moved through, in time order
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    status     TEXT NOT NULL,  -- pending|paid|shipped|delivered|cancelled|refunded
    changed_at TEXT NOT NULL  -- timestamp the order entered this status
);

CREATE TABLE order_coupons (  -- Coupons redeemed on an order
    order_id  INTEGER NOT NULL REFERENCES orders(id),
    coupon_id INTEGER NOT NULL REFERENCES coupons(id),
    PRIMARY KEY (order_id, coupon_id)
);

CREATE TABLE payments (  -- Payment attempts and refunds; an order can have several rows
    id       INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    method   TEXT NOT NULL,  -- card|paypal|apple_pay|bank_transfer|gift_card
    provider TEXT NOT NULL,  -- stripe|paypal|adyen
    amount   REAL NOT NULL,  -- in orders.currency; for status 'refunded' the amount returned to the customer
    fee      REAL NOT NULL DEFAULT 0,  -- processing fee charged by the provider, in orders.currency
    status   TEXT NOT NULL,  -- captured|failed|refunded
    paid_at  TEXT NOT NULL  -- timestamp of the attempt or refund
);

CREATE TABLE shipments (  -- Parcels sent for an order
    id              INTEGER PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(id),
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id),
    carrier         TEXT NOT NULL,  -- UPS|FedEx|USPS|Canada Post|Royal Mail|DPD|DHL|Australia Post
    service_level   TEXT NOT NULL,  -- standard|express
    tracking_number TEXT,
    status          TEXT NOT NULL,  -- in_transit|delivered
    shipping_cost   REAL NOT NULL,  -- what the carrier charged us, in USD
    shipped_at      TEXT NOT NULL,  -- timestamp
    promised_at     TEXT NOT NULL,  -- promised delivery date; delivered_at later than this means late
    delivered_at    TEXT  -- timestamp; NULL while in transit
);

CREATE TABLE returns (  -- Return requests (RMAs) against delivered orders
    id            INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(id),
    status        TEXT NOT NULL,  -- requested|approved|rejected|refunded
    reason        TEXT NOT NULL,  -- too_small|too_large|defective|damaged_in_transit|not_as_described|wrong_item|changed_mind|late_delivery
    requested_at  TEXT NOT NULL,  -- timestamp
    resolved_at   TEXT,  -- timestamp the return was rejected or refunded
    refund_amount REAL  -- in orders.currency; set when status = 'refunded'
);

CREATE TABLE return_items (  -- Order lines included in a return
    id            INTEGER PRIMARY KEY,
    return_id     INTEGER NOT NULL REFERENCES returns(id),
    order_item_id INTEGER NOT NULL REFERENCES order_items(id),
    quantity      INTEGER NOT NULL,  -- units returned (at most the line quantity)
    condition     TEXT NOT NULL  -- unopened|opened|damaged
);

-- ---------------------------------------------------------------------------------------
-- Shopping behaviour
-- ---------------------------------------------------------------------------------------

CREATE TABLE carts (  -- Shopping carts; a converted cart became an order, an abandoned one did not
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status      TEXT NOT NULL,  -- active|abandoned|converted
    created_at  TEXT NOT NULL,  -- timestamp
    updated_at  TEXT NOT NULL,  -- timestamp of the last change
    order_id    INTEGER REFERENCES orders(id)  -- resulting order when status = 'converted'
);

CREATE TABLE cart_items (  -- Variants placed in a cart
    id         INTEGER PRIMARY KEY,
    cart_id    INTEGER NOT NULL REFERENCES carts(id),
    variant_id INTEGER NOT NULL REFERENCES product_variants(id),
    quantity   INTEGER NOT NULL,
    added_at   TEXT NOT NULL  -- timestamp
);

CREATE TABLE wishlist_items (  -- Products a customer saved for later
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    product_id  INTEGER NOT NULL REFERENCES products(id),
    added_at    TEXT NOT NULL,  -- timestamp
    PRIMARY KEY (customer_id, product_id)
);

CREATE TABLE reviews (  -- Product ratings written by customers
    id                   INTEGER PRIMARY KEY,
    product_id           INTEGER NOT NULL REFERENCES products(id),
    customer_id          INTEGER NOT NULL REFERENCES customers(id),
    order_id             INTEGER REFERENCES orders(id),  -- purchase being reviewed; NULL when unverified
    rating               INTEGER NOT NULL,  -- 1..5
    title                TEXT,
    body                 TEXT,
    is_verified_purchase INTEGER NOT NULL DEFAULT 0,  -- 0/1
    helpful_votes        INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL  -- timestamp
);

-- ---------------------------------------------------------------------------------------
-- Support and finance
-- ---------------------------------------------------------------------------------------

CREATE TABLE support_tickets (  -- Customer service cases
    id                 INTEGER PRIMARY KEY,
    customer_id        INTEGER NOT NULL REFERENCES customers(id),
    order_id           INTEGER REFERENCES orders(id),  -- related order, if any
    category           TEXT NOT NULL,  -- shipping_delay|damaged_item|return_request|payment_issue|product_question|account
    priority           TEXT NOT NULL,  -- low|medium|high|urgent
    channel            TEXT NOT NULL,  -- email|chat|phone
    status             TEXT NOT NULL,  -- open|pending|resolved|closed
    created_at         TEXT NOT NULL,  -- timestamp
    first_response_at  TEXT,  -- timestamp of the first agent reply
    resolved_at        TEXT,  -- timestamp; NULL while open or pending
    satisfaction_score INTEGER  -- post-resolution survey 1..5; NULL if not answered
);

CREATE TABLE exchange_rates (  -- Monthly FX rates for converting order money to USD
    currency    TEXT NOT NULL,  -- USD|EUR|GBP|CAD|AUD
    rate_date   TEXT NOT NULL,  -- first day of the month, e.g. '2025-03-01'
    rate_to_usd REAL NOT NULL,  -- USD value of 1 unit of currency (1.0 for USD)
    PRIMARY KEY (currency, rate_date)
);

-- ---------------------------------------------------------------------------------------
-- Indexes on foreign keys and common filters
-- ---------------------------------------------------------------------------------------

CREATE INDEX idx_categories_parent ON categories(parent_id);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_brand ON products(brand_id);
CREATE INDEX idx_products_supplier ON products(supplier_id);
CREATE INDEX idx_price_history_product ON product_price_history(product_id, valid_from);
CREATE INDEX idx_variants_product ON product_variants(product_id);
CREATE INDEX idx_inventory_variant ON inventory(variant_id);
CREATE INDEX idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX idx_po_supplier ON purchase_orders(supplier_id);
CREATE INDEX idx_po_items_po ON purchase_order_items(purchase_order_id);
CREATE INDEX idx_po_items_variant ON purchase_order_items(variant_id);
CREATE INDEX idx_customers_created ON customers(created_at);
CREATE INDEX idx_addresses_customer ON addresses(customer_id);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_placed_at ON orders(placed_at);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_variant ON order_items(variant_id);
CREATE INDEX idx_status_history_order ON order_status_history(order_id);
CREATE INDEX idx_payments_order ON payments(order_id);
CREATE INDEX idx_shipments_order ON shipments(order_id);
CREATE INDEX idx_returns_order ON returns(order_id);
CREATE INDEX idx_return_items_return ON return_items(return_id);
CREATE INDEX idx_carts_customer ON carts(customer_id);
CREATE INDEX idx_cart_items_cart ON cart_items(cart_id);
CREATE INDEX idx_reviews_product ON reviews(product_id);
CREATE INDEX idx_reviews_customer ON reviews(customer_id);
CREATE INDEX idx_tickets_customer ON support_tickets(customer_id);
CREATE INDEX idx_tickets_order ON support_tickets(order_id);
