"""
SQLite schema and all read/write operations.
Single file — keeps it simple and cheap.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from config.settings import DB_PATH
from src.utils.logger import logger


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist yet."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            product_id   TEXT PRIMARY KEY,
            brand        TEXT NOT NULL,
            model        TEXT NOT NULL,
            variant      TEXT,
            barcode_ean  TEXT,
            keywords     TEXT,
            baseline_price REAL,
            discount_threshold REAL NOT NULL DEFAULT 25,
            active       INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS price_snapshots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id   TEXT NOT NULL,
            retailer     TEXT NOT NULL,
            title        TEXT,
            url          TEXT,
            price        REAL NOT NULL,
            in_stock     INTEGER NOT NULL DEFAULT 1,
            checked_at   TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id      TEXT NOT NULL,
            retailer        TEXT NOT NULL,
            old_price       REAL,
            new_price       REAL NOT NULL,
            discount_pct    REAL NOT NULL,
            url             TEXT,
            sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );

        CREATE TABLE IF NOT EXISTS run_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      TEXT NOT NULL,
            retailer    TEXT,
            checked     INTEGER DEFAULT 0,
            matched     INTEGER DEFAULT 0,
            alerts_sent INTEGER DEFAULT 0,
            failed      INTEGER DEFAULT 0,
            started_at  TEXT NOT NULL,
            finished_at TEXT,
            notes       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_product_retailer
            ON price_snapshots(product_id, retailer, checked_at);
        CREATE INDEX IF NOT EXISTS idx_alerts_product_retailer
            ON alerts(product_id, retailer, sent_at);
        """)
    logger.debug("DB initialised")


# ── Products ─────────────────────────────────────────────────────────────────

def upsert_products(rows: list[dict]):
    """Insert or update products from the Excel source."""
    sql = """
        INSERT INTO products
            (product_id, brand, model, variant, barcode_ean, keywords,
             baseline_price, discount_threshold, active, updated_at)
        VALUES
            (:product_id, :brand, :model, :variant, :barcode_ean, :keywords,
             :baseline_price, :discount_threshold, :active, datetime('now'))
        ON CONFLICT(product_id) DO UPDATE SET
            brand=excluded.brand, model=excluded.model,
            variant=excluded.variant, barcode_ean=excluded.barcode_ean,
            keywords=excluded.keywords, baseline_price=excluded.baseline_price,
            discount_threshold=excluded.discount_threshold,
            active=excluded.active, updated_at=excluded.updated_at
    """
    with get_conn() as conn:
        conn.executemany(sql, rows)
    logger.debug(f"Upserted {len(rows)} products")


def get_active_products() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM products WHERE active=1 ORDER BY brand, model"
        ).fetchall()
    return [dict(r) for r in rows]


def set_baseline(product_id: str, price: float):
    """Set baseline price if not already set."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET baseline_price=? WHERE product_id=? AND baseline_price IS NULL",
            (price, product_id),
        )


# ── Price snapshots ───────────────────────────────────────────────────────────

def save_snapshot(product_id: str, retailer: str, title: str,
                  url: str, price: float, in_stock: bool):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO price_snapshots
               (product_id, retailer, title, url, price, in_stock)
               VALUES (?,?,?,?,?,?)""",
            (product_id, retailer, title, url, price, int(in_stock)),
        )


def get_baseline_price(product_id: str) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT baseline_price FROM products WHERE product_id=?",
            (product_id,),
        ).fetchone()
    return row["baseline_price"] if row else None


# ── Alerts ────────────────────────────────────────────────────────────────────

def was_alerted_recently(product_id: str, retailer: str, cooldown_hours: int) -> bool:
    cutoff = (datetime.utcnow() - timedelta(hours=cooldown_hours)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT 1 FROM alerts
               WHERE product_id=? AND retailer=? AND sent_at > ?
               LIMIT 1""",
            (product_id, retailer, cutoff),
        ).fetchone()
    return row is not None


def save_alert(product_id: str, retailer: str, old_price: float | None,
               new_price: float, discount_pct: float, url: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO alerts
               (product_id, retailer, old_price, new_price, discount_pct, url)
               VALUES (?,?,?,?,?,?)""",
            (product_id, retailer, old_price, new_price, discount_pct, url),
        )


# ── Run logs ──────────────────────────────────────────────────────────────────

def start_run_log(run_id: str, retailer: str, started_at: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO run_logs (run_id, retailer, started_at) VALUES (?,?,?)",
            (run_id, retailer, started_at),
        )
        return cur.lastrowid


def finish_run_log(log_id: int, stats: dict, notes: str = ""):
    with get_conn() as conn:
        conn.execute(
            """UPDATE run_logs SET
               checked=?, matched=?, alerts_sent=?, failed=?,
               finished_at=datetime('now'), notes=?
               WHERE id=?""",
            (stats["checked"], stats["matched"],
             stats["alerts_sent"], stats["failed"], notes, log_id),
        )
