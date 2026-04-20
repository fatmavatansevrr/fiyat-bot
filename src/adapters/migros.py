"""
Migros adapter — Playwright tabanlı (Angular SPA, HTTP ile çalışmıyor).

Doğrulanmış selektorlar (canlı test, 2026-04-20):
  Kart    : fe-product-card
  Başlık  : img.product-image[alt]
  Fiyat   : fe-product-price  →  "799,95 TL"
  URL     : a#product-image-link[href]
  Stok    : [class*="out-of-stock"] yoksa stokta
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from src.adapters.base import BaseAdapter
from src.utils.logger import logger


class MigrosAdapter(BaseAdapter):
    retailer = "migros"
    base_url = "https://www.migros.com.tr"

    async def ensure_region(self) -> bool:
        # Angular SPA — mağaza seçimi oturum gerektiriyor, public fiyatlar kullanılıyor
        return True

    async def search_product(self, product: dict) -> dict | None:
        query = _build_query(product)
        url = f"https://www.migros.com.tr/arama?q={quote_plus(query)}"
        logger.debug(f"[migros] Arama: {query}")

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Angular'ın render etmesini bekle (fix wait yerine akıllı bekleme)
            try:
                await self.page.wait_for_selector("fe-product-card", timeout=9000)
            except Exception:
                logger.warning(f"[migros] Ürün kartı yüklenemedi: {query}")
                await self._screenshot(f"timeout_{product['product_id']}")
                return None

            await self._accept_cookies()

            cards = await self.page.locator("fe-product-card").all()
            if not cards:
                logger.warning(f"[migros] Sonuç yok: {query}")
                return None

            best_score, best = 0, None
            for card in cards[:8]:
                try:
                    # Başlık — img alt attribute
                    img = card.locator("img.product-image")
                    if await img.count() == 0:
                        continue
                    title = (await img.first.get_attribute("alt") or "").strip()
                    if not title:
                        continue

                    # Fiyat — fe-product-price
                    price_el = card.locator("fe-product-price")
                    if await price_el.count() == 0:
                        continue
                    price = _parse_price(await price_el.first.inner_text(timeout=3000))
                    if price is None:
                        continue

                    # URL
                    href = await card.locator("a#product-image-link").get_attribute("href", timeout=3000) or ""
                    full_url = (
                        f"https://www.migros.com.tr{href}" if href.startswith("/") else href
                    )

                    # Stok
                    in_stock = await card.locator('[class*="out-of-stock"]').count() == 0

                    score = self.score_match(title, product)
                    logger.debug(f"  {score:3d} | {price:>9.2f} TL | {title[:55]}")
                    if score > best_score:
                        best_score = score
                        best = {"title": title, "url": full_url,
                                "price": price, "in_stock": in_stock}

                except Exception as e:
                    logger.debug(f"  [migros] kart atlandı: {e}")
                    continue

            if best and best_score >= 40:
                logger.info(f"[migros] {best['price']:.2f} TL  score={best_score}  {best['title'][:50]}")
                return best

            logger.warning(f"[migros] Güvenilir eşleşme yok (score={best_score}): {query}")
            return None

        except Exception as e:
            logger.error(f"[migros] Hata: {e}")
            await self._screenshot(f"error_{product['product_id']}")
            return None


def _build_query(p: dict) -> str:
    return " ".join(x for x in [p["brand"], p["model"], p.get("variant")] if x)


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    # "799,95 TL" → "79995" → "799.95" → 799.95
    cleaned = re.sub(r"[^\d,]", "", text.strip()).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
