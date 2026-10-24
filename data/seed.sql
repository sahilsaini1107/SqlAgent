-- Deterministic seed data. Covers: multiple states (incl. California), a customer with a
-- NULL address, customers with no orders, orders with several items, a boundary sign-up date
-- (2024-01-01), and every order status.

INSERT INTO customers (id, name, state, email, created_at) VALUES
    (1, 'Alice Nguyen',   'CA',  'alice@example.com', '2023-11-02'),
    (2, 'Bob Martin',     'NY',  'bob@example.com',   '2024-01-15'),
    (3, 'Carol Diaz',     'CA',  'carol@example.com', '2024-03-20'),
    (4, 'Dan O''Neill',   'TX',  'dan@example.com',   '2022-07-09'),
    (5, 'Eve Thompson',   'WA',  'eve@example.com',   '2024-06-01'),  -- no orders
    (6, 'Frank Li',       'CA',  'frank@example.com', '2024-02-10'),
    (7, 'Grace Hopper',   NULL,  'grace@example.com', '2023-05-30'),  -- NULL state, no orders
    (8, 'Heidi Schmidt',  'NY',  'heidi@example.com', '2024-01-01');  -- boundary date

INSERT INTO products (id, name, category, unit_price) VALUES
    (1, 'Widget',       'Hardware',    9.99),
    (2, 'Gadget',       'Hardware',    19.50),
    (3, 'Gizmo',        'Electronics', 49.00),
    (4, 'Doohickey',    'Electronics', 5.25),
    (5, 'Thingamajig',  'Office',      2.00),
    (6, 'Contraption',  'Office',      120.00);

INSERT INTO orders (id, customer_id, ordered_at, status) VALUES
    (1, 1, '2024-02-01', 'shipped'),
    (2, 1, '2024-05-12', 'delivered'),
    (3, 2, '2024-01-20', 'pending'),
    (4, 3, '2024-04-02', 'shipped'),
    (5, 4, '2023-12-15', 'delivered'),
    (6, 6, '2024-02-11', 'cancelled'),
    (7, 8, '2024-01-05', 'shipped'),
    (8, 3, '2024-07-01', 'pending');

INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES
    (1,  1, 1, 2, 9.99),
    (2,  1, 3, 1, 49.00),
    (3,  2, 2, 3, 19.50),
    (4,  3, 4, 10, 5.25),
    (5,  4, 3, 1, 49.00),
    (6,  4, 5, 5, 2.00),
    (7,  5, 6, 1, 120.00),
    (8,  6, 1, 1, 9.99),
    (9,  7, 2, 2, 19.50),
    (10, 7, 4, 4, 5.25),
    (11, 8, 5, 20, 2.00);
