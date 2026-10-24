-- SQL Agent — sample commerce schema (synthetic; stands in for a provided schema).
-- Read-only target database for the agent. Chosen to exercise joins, aggregation,
-- date filters, and one-to-many fan-out (orders -> order_items).

PRAGMA foreign_keys = ON;

CREATE TABLE customers (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    state    TEXT,                 
    email      TEXT UNIQUE,
    created_at TEXT NOT NULL         
);

CREATE TABLE products (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL,
    unit_price REAL NOT NULL        
);

CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    ordered_at  TEXT NOT NULL,       
    status      TEXT NOT NULL        -- pending | shipped | delivered | cancelled
);

CREATE TABLE order_items (
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity   INTEGER NOT NULL,
    unit_price REAL NOT NULL         -- price captured at order time (may differ from list)
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_ordered_at ON orders(ordered_at);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
