"""
Ana orkestratör — paralel market + eşzamanlı ürün mimarisi.

Önceki mimari (yavaş):
  market_1 → ürün_1, ürün_2, ürün_3 ...
  market_2 → ürün_1, ürün_2, ürün_3 ...   ← market_1 bitene kadar bekler
  ...

Yeni mimari (hızlı):
  ┌─ market_1 ─┐   ┌─ market_2 ─┐   ┌─ market_3 ─┐
  │ ü1 ü2 ü3   │   │ ü1 ü2 ü3   │   │ ü1 ü2 ü3   │  ← hepsi aynı anda
  └────────────┘   └────────────┘   └────────────┘

HTTP adaptörler (Trendyol, Migros, Gürmar):
  → concurrency=5: market başına 5 ürün aynı anda

Playwright adaptörler (Amazon, Carrefour):
  → concurrency=1: tek sayfa, sıralı ama kaynaklar engelli → hızlı

100 ürün tahmin süresi:
  HTTP marketler  : ~15-25 saniye
  Playwright mkt  : ~3-4 dakika
  Toplam (paralel): max(HTTP, Playwright) ≈ 3-4 dakika
  Eski sistem     : ~80 dakika
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime

from src.utils.logger import logger
from src.storage.database import init_db, start_run_log, finish_run_log
from src.storage.product_source import load_inventory
from src.core.discount import evaluate
from src.notifications.telegram import send_alert, send_summary
from config.settings import ENABLED_RETAILERS


def _get_adapter(retailer_name: str):
    if retailer_name == "trendyol":
        from src.adapters.trendyol import TrendyolAdapter
        return TrendyolAdapter()
    if retailer_name == "amazon":
        from src.adapters.amazon import AmazonAdapter
        return AmazonAdapter(headless=True)
    if retailer_name == "migros":
        from src.adapters.migros import MigrosAdapter
        return MigrosAdapter()
    if retailer_name == "carrefour":
        from src.adapters.carrefour import CarrefourAdapter
        return CarrefourAdapter(headless=True)
    if retailer_name == "gurmar":
        from src.adapters.gurmar import GurmarAdapter
        return GurmarAdapter()
    return None


class Orchestrator:
    def __init__(self):
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.stats = {"checked": 0, "matched": 0, "alerts_sent": 0, "failed": 0}
        self.retailer_details: list[dict] = []
        self._stats_lock = asyncio.Lock()

    async def run(self):
        logger.info(f"=== Price Monitor Run {self.run_id} başladı ===")
        init_db()

        products = load_inventory()
        if not products:
            logger.warning("Aktif ürün bulunamadı. Çıkılıyor.")
            return

        logger.info(f"{len(products)} aktif ürün yüklendi.")

        # Tüm marketleri AYNI ANDA başlat
        retailer_tasks = [
            self._run_retailer(name, products)
            for name, enabled in ENABLED_RETAILERS.items()
            if enabled
        ]
        await asyncio.gather(*retailer_tasks, return_exceptions=True)

        await send_summary(self.run_id, self.stats, self.retailer_details)
        self._print_summary()

    async def _run_retailer(self, retailer_name: str, products: list[dict]):
        logger.info(f"--- Market başladı: {retailer_name} ---")
        started = datetime.utcnow().isoformat()
        log_id = start_run_log(self.run_id, retailer_name, started)
        rs = {"retailer": retailer_name, "checked": 0, "matched": 0,
              "alerts_sent": 0, "failed": 0}

        adapter = _get_adapter(retailer_name)
        if adapter is None:
            logger.warning(f"[{retailer_name}] Adaptör bulunamadı — atlandı")
            finish_run_log(log_id, rs)
            return

        # adaptörün concurrency değerini oku (HTTPAdapter=5, BaseAdapter=1)
        concurrency = getattr(adapter, "concurrency", 1)
        sem = asyncio.Semaphore(concurrency)

        logger.info(f"[{retailer_name}] Eşzamanlılık: {concurrency} ürün/an, toplam {len(products)} ürün")

        try:
            async with adapter as a:
                await a.ensure_region()

                async def process_one(product: dict):
                    label = f"{product['brand']} {product['model']}"
                    async with sem:
                        rs["checked"] += 1
                        try:
                            result = await a.search_product(product)

                            if result is None:
                                rs["failed"] += 1
                                return

                            rs["matched"] += 1
                            should_alert, alert_data = evaluate(
                                product=product,
                                retailer=retailer_name,
                                title=result["title"],
                                url=result["url"],
                                price=result["price"],
                                in_stock=result["in_stock"],
                            )

                            if should_alert and alert_data:
                                await send_alert(
                                    product=product,
                                    retailer=retailer_name,
                                    old_price=alert_data["old_price"],
                                    new_price=alert_data["new_price"],
                                    discount_pct=alert_data["discount_pct"],
                                    url=result["url"],
                                    title=result["title"],
                                )
                                rs["alerts_sent"] += 1

                            # HTTP adaptörler: hafif rastgele bekleme (bot tespitini zorlaştırır)
                            # Playwright adaptörler: concurrency=1 olduğu için zaten sıralı
                            if concurrency > 1:
                                await asyncio.sleep(random.uniform(0.2, 0.7))

                        except Exception as e:
                            logger.error(f"[{retailer_name}] {label} hatası: {e}")
                            rs["failed"] += 1

                # Tüm ürünleri eşzamanlı olarak işle (semaphore akış kontrolü yapar)
                await asyncio.gather(
                    *[process_one(p) for p in products],
                    return_exceptions=True,
                )

        except Exception as e:
            logger.error(f"[{retailer_name}] Adaptör çöktü: {e}")
            rs["failed"] += len(products)

        finish_run_log(log_id, rs)
        self.retailer_details.append(rs)

        # Global istatistikleri güncelle (lock ile thread-safe)
        async with self._stats_lock:
            for k in ("checked", "matched", "alerts_sent", "failed"):
                self.stats[k] += rs[k]

        logger.info(
            f"--- {retailer_name} bitti | "
            f"kontrol={rs['checked']} eşleşme={rs['matched']} "
            f"alert={rs['alerts_sent']} hata={rs['failed']} ---"
        )

    def _print_summary(self):
        s = self.stats
        logger.info(
            f"=== Çalışma tamamlandı | "
            f"kontrol={s['checked']} eşleşme={s['matched']} "
            f"alert={s['alerts_sent']} hata={s['failed']} ==="
        )
