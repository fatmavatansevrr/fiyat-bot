"""
Gürmar adapter — Playwright tabanlı (React/Ant Design SPA, HTTP ile çalışmıyor).

Doğrulanmış selektorlar (canlı test, 2026-04-20):
  Kart    : .product-vertical          (25 adet bulundu)
  Başlık  : h4 içindeki metin
  Fiyat   : .product-price             →  "₺20,00"
  URL     : a.product-detail-link[href]
  Stok    : her zaman stokta (OOS göstergesi yok)

NOT: Gürmar yerel bir market (İzmir). Elektronik değil, gıda ve market ürünleri
satar. Bu adaptörü sadece Gürmar'da satılan ürünler için etkinleştirin.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from src.adapters.base import BaseAdapter
from src.utils.logger import logger


class GurmarAdapter(BaseAdapter):
    retailer = "gurmar"
    base_url = "https://www.gurmar.com.tr"

    async def ensure_region(self) -> bool:
        return True  # Gürmar zaten İzmir'e özel

    async def search_product(self, product: dict) -> dict | None:
        # Türkçe karakter sorunu + Gürmar'ın arama motoru için marka yeterli;
        # score_match doğru ürünü filtreler
        query = product["brand"]
        url = f"https://www.gurmar.com.tr/arama?q={quote_plus(query)}"
        logger.debug(f"[gurmar] Arama: {query}")

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # React'ın render etmesini bekle
            try:
                await self.page.wait_for_selector(".product-vertical", timeout=10000)
            except Exception:
                logger.warning(f"[gurmar] Ürün kartı yüklenemedi: {query}")
                await self._screenshot(f"timeout_{product['product_id']}")
                return None

            cards = await self.page.locator(".product-vertical").all()
            if not cards:
                logger.warning(f"[gurmar] Sonuç yok: {query}")
                return None

            best_score, best = 0, None
            for card in cards[:8]:
                try:
                    # Başlık — h4 elementi
                    h4 = card.locator("h4")
                    if await h4.count() == 0:
                        continue
                    title = (await h4.first.inner_text(timeout=3000)).strip()
                    if not title:
                        continue

                    # Fiyat — .product-price → "₺20,00"
                    price_el = card.locator(".product-price")
                    if await price_el.count() == 0:
                        continue
                    price = _parse_price(await price_el.first.inner_text(timeout=3000))
                    if price is None:
                        continue

                    # URL
                    href = (
                        await card.locator("a.product-detail-link").get_attribute("href", timeout=3000)
                        or ""
                    )
                    full_url = (
                        f"https://www.gurmar.com.tr{href}" if href.startswith("/") else href
                    )

                    score = self.score_match(title, product)
                    logger.debug(f"  {score:3d} | {price:>9.2f} TL | {title[:55]}")
                    if score > best_score:
                        best_score = score
                        best = {"title": title, "url": full_url,
                                "price": price, "in_stock": True}

                except Exception as e:
                    logger.debug(f"  [gurmar] kart atlandı: {e}")
                    continue

            if best and best_score >= 40:
                logger.info(f"[gurmar] {best['price']:.2f} TL  score={best_score}  {best['title'][:50]}")
                return best

            logger.warning(f"[gurmar] Güvenilir eşleşme yok (score={best_score}): {query}")
            return None

        except Exception as e:
            logger.error(f"[gurmar] Hata: {e}")
            await self._screenshot(f"error_{product['product_id']}")
            return None


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    # "₺20,00" veya "₺1.234,56" → 20.0 veya 1234.56
    cleaned = re.sub(r"[^\d,]", "", text.strip())
    # Bin ayracı nokta kullanıyorsa temizle (örn. "1.234,56" → "1234,56")
    if cleaned.count(",") == 1 and "." in cleaned:
        cleaned = cleaned.replace(".", "")
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
