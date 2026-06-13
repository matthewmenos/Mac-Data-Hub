USER_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Mirror of orders placed through this reseller's store
CREATE TABLE IF NOT EXISTS orders (
    id                  TEXT PRIMARY KEY,   -- matches global orders.id
    bundle_label        TEXT NOT NULL,
    network             TEXT NOT NULL,
    customer_phone      TEXT NOT NULL,
    amount_pesewas      INTEGER NOT NULL,
    profit_pesewas      INTEGER NOT NULL,
    status              TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Earnings log per transaction
CREATE TABLE IF NOT EXISTS earnings (
    id             TEXT PRIMARY KEY,
    order_id       TEXT NOT NULL REFERENCES orders(id),
    amount_pesewas INTEGER NOT NULL,
    recorded_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
