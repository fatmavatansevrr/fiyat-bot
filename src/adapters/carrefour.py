"""
CarrefourSA adapter — Playwright tabanlı.

Doğrulanmış selektorlar (canlı test, 2026-04-20):
  Kart    : .product-card              (30 adet bulundu)
  Başlık  : h3.item-name
  Fiyat   : [data-price] attribute     →  31999.00  (en güvenilir)
            span.item-price text       →  "31.999,00 TL"  (yedek)
  URL     : a.product-return[href]
  Stok    : [class*="out-of-stock"] yoksa stokta
  Çerez   : button#accept (base._accept_cookies'e eklendi)
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from src.adapters.base import BaseAdapter
from src.utils.logger import logger


class CarrefourAdapter(BaseAdapter):
    retailer = "carrefour"
    base_url = "https://www.carrefoursa.com"

    async def ensure_region(self) -> bool:
        return True

    async def search_product(self, product: dict) -> dict | None:
        query = _build_query(product)
        url = f"https://www.carrefoursa.com/search?text={quote_plus(query)}"
        logger.debug(f"[carrefour] Arama: {query}")

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Çerez popup'ını kapat (button#accept)
            await self._accept_cookies()

            # Ürün kartlarının yüklenmesini akıllıca bekle
            try:
                await self.page.wait_for_selector(".product-card", timeout=8000)
            except Exception:
                logger.warning(f"[carrefour] Ürün kartı yüklenemedi: {query}")
                await self._screenshot(f"timeout_{product['product_id']}")
                return None

            cards = await self.page.locator(".product-card").all()
            if not cards:
                logger.warning(f"[carrefour] Sonuç yok: {query}")
                return None

            best_score, best = 0, None
            for card in cards[:8]:
                try:
                    # Başlık
                    title_el = card.locator("h3.item-name")
                    if await title_el.count() == 0:
                        continue
                    title = (await title_el.first.inner_text(timeout=3000)).strip()

                    # Fiyat — data-price attribute en güvenilir
                    price: float | None = None
                    data_el = card.locator("[data-price]")
                    if await data_el.count() > 0:
                        raw = await data_el.first.get_attribute("data-price") or ""
                        try:
                            price = float(raw)
                        except ValueError:
                            price = None

                    if price is None:
                        # Yedek: span.item-price metni → "31.999,00 TL"
                        price_el = card.locator("span.item-price")
                        if await price_el.count() > 0:
                            price = _parse_price(await price_el.first.inner_text(timeout=3000))

                    if price is None:
                        continue

                    # URL
                    href = await card.locator("a.product-return").get_attribute("href", timeout=3000) or ""
                    full_url = href if href.startswith("http") else f"https://www.carrefoursa.com{href}"

                    # Stok
                    in_stock = await card.locator('[class*="out-of-stock"]').count() == 0

                    score = self.score_match(title, product)
                    logger.debug(f"  {score:3d} | {price:>9.2f} TL | {title[:55]}")
                    if score > best_score:
                        best_score = score
                        best = {"title": title, "url": full_url,
                                "price": price, "in_stock": in_stock}

                except Exception as e:
                    logger.debug(f"  [carrefour] kart atlandı: {e}")
                    continue

            if best and best_score >= 40:
                logger.info(f"[carrefour] {best['price']:.2f} TL  score={best_score}  {best['title'][:50]}")
                return best

            logger.warning(f"[carrefour] Güvenilir eşleşme yok (score={best_score}): {query}")
            return None

        except Exception as e:
            logger.error(f"[carrefour] Hata: {e}")
            await self._screenshot(f"error_{product['product_id']}")
            return None


def _build_query(p: dict) -> str:
    return " ".join(x for x in [p["brand"], p["model"], p.get("variant")] if x)


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    # "31.999,00 TL" → "31999.00" → 31999.0
    # Nokta: binlik ayracı; virgül: ondalık ayracı
    cleaned = re.sub(r"[^\d.,]", "", text.strip())
    # Eğer hem nokta hem virgül varsa: nokta=binlik, virgül=ondalık
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
