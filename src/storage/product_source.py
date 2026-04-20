"""
Reads inventory.xlsx and syncs products into the DB.
Column names in the Excel must match the schema exactly.
"""
import pandas as pd
from pathlib import Path

from config.settings import INVENTORY_PATH
from src.storage.database import upsert_products
from src.utils.logger import logger

REQUIRED_COLS = {"product_id", "brand", "model", "active"}

DEFAULTS = {
    "variant": None,
    "barcode_ean": None,
    "keywords": None,
    "baseline_price": None,
    "discount_threshold": 25.0,
    "active": 1,
}


def load_inventory() -> list[dict]:
    """Read Excel, validate, sync to DB, return active product dicts."""
    if not INVENTORY_PATH.exists():
        logger.warning(f"Inventory file not found: {INVENTORY_PATH}")
        return []

    df = pd.read_excel(INVENTORY_PATH, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        logger.error(f"Inventory missing required columns: {missing}")
        return []

    rows = []
    for _, row in df.iterrows():
        r = dict(DEFAULTS)
        for col in df.columns:
            val = row.get(col)
            if pd.isna(val) or val == "":
                val = DEFAULTS.get(col)
            r[col] = val

        # Type coercions
        try:
            r["product_id"] = str(r["product_id"]).strip()
            r["brand"] = str(r["brand"]).strip()
            r["model"] = str(r["model"]).strip()
            r["active"] = 1 if str(r.get("active", "1")).strip() in ("1", "true", "True", "yes") else 0
            r["baseline_price"] = float(r["baseline_price"]) if r["baseline_price"] is not None else None
            r["discount_threshold"] = float(r["discount_threshold"]) if r["discount_threshold"] is not None else 25.0
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping row {r.get('product_id')}: {e}")
            continue

        rows.append(r)

    if rows:
        upsert_products(rows)
        logger.info(f"Loaded {len(rows)} products from inventory ({sum(r['active'] for r in rows)} active)")

    return [r for r in rows if r["active"] == 1]
