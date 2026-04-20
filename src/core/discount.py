"""
Compares current price against baseline and decides whether to alert.
Returns (should_alert: bool, alert_data: dict | None)
"""
from __future__ import annotations

from src.storage.database import (
    get_baseline_price, set_baseline,
    save_snapshot, save_alert, was_alerted_recently,
)
from src.utils.logger import logger
from config.settings import ALERT_COOLDOWN_HOURS


def evaluate(
    product: dict,
    retailer: str,
    title: str,
    url: str,
    price: float,
    in_stock: bool,
) -> tuple[bool, dict | None]:
    pid = product["product_id"]
    threshold = float(product.get("discount_threshold") or 25.0)

    save_snapshot(pid, retailer, title, url, price, in_stock)

    baseline = get_baseline_price(pid)

    if baseline is None:
        set_baseline(pid, price)
        logger.info(f"[{retailer}] Baseline set → {product['brand']} {product['model']}: {price:.2f} TL")
        return False, None

    if baseline <= 0:
        logger.warning(f"[{retailer}] Invalid baseline for {pid}: {baseline}")
        return False, None

    drop_pct = (baseline - price) / baseline * 100

    logger.debug(
        f"[{retailer}] {product['brand']} {product['model']} | "
        f"baseline={baseline:.2f}  now={price:.2f}  drop={drop_pct:.1f}%  threshold={threshold}%"
    )

    if drop_pct >= threshold:
        if was_alerted_recently(pid, retailer, ALERT_COOLDOWN_HOURS):
            logger.debug(f"[{retailer}] {pid} cooldown active — skipping alert")
            return False, None

        save_alert(pid, retailer, baseline, price, drop_pct, url)
        alert_data = {
            "old_price": baseline,
            "new_price": price,
            "discount_pct": drop_pct,
        }
        logger.info(
            f"[{retailer}] ALERT {product['brand']} {product['model']} "
            f"{baseline:.2f} → {price:.2f} TL  (-%{drop_pct:.1f})"
        )
        return True, alert_data

    return False, None
