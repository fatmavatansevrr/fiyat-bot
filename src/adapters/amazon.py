"""
Amazon.com.tr adapter — Playwright tabanlı (bot tespiti çok sıkı).

Performans iyileştirmeleri (BaseAdapter'dan miras alır):
  - Resim/CSS/font engelleme → sayfa yükü ~3x hızlı
  - Bekleme süreleri optimize edildi (2500ms → 900ms)
  - Ürünler arası uyku kaldırıldı (orchestrator yönetiyor)
"""
from __future__ import annotations
import re

from playwright.async_api import TimeoutError as PWTimeout

from src.adapters.base import BaseAdapter
from src.utils.logger import logger

IZMIR_POSTAL = "35220"


class AmazonAdapter(BaseAdapter):
    retailer = "amazon"
    base_url = "https://www.amazon.com.tr"

    async def ensure_region(self) -> bool:
        try:
            await self.page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
            await self._wait(1500)
            await self._accept_cookies()

            loc = self.page.locator("#glow-ingress-line2, #nav-global-location-slot")
            if await loc.count() > 0:
                text = await loc.first.inner_text()
                if "35" in text:
                    logger.debug("[amazon] Bölge zaten İzmir")
                    self.region_set = True
                    return True

            await self.page.click(
                "#nav-global-location-popover-link, #glow-ingress-block",
                timeout=5000,
            )
            await self._wait(1200)

            for sel in [
                "input#GLUXZipUpdateInput",
                "input[data-testid='GLUXZipUpdateInput']",
                "input[placeholder*='posta']",
                ".a-popover-inner input[type='text']",
            ]:
                try:
                    await self._slow_type(sel, IZMIR_POSTAL)
                    await self._wait(400)
                    await self.page.click(
                        "input#GLUXZipUpdate, "
                        "button#GLUXZipUpdate, "
                        "[data-action='GLUXPostalUpdateAction'] input",
                        timeout=3000,
                    )
                    await self._wait(1000)
                    try:
                        await self.page.click(
                            "button[name='glowDoneButton'], "
                            ".a-popover-footer .a-button-primary",
                            timeout=3000,
                        )
                    except PWTimeout:
                        pass
                    await self._wait(1000)
                    logger.info(f"[amazon] Bölge ayarlandı — posta kodu {IZMIR_POSTAL} (İzmir)")
                    self.region_set = True
                    return True
                except PWTimeout:
                    continue

        except Exception as e:
            logger.warning(f"[amazon] ensure_region hatası: {e}")

        logger.warning("[amazon] Bölge doğrulanamadı — devam ediliyor")
        return True

    async def search_product(self, product: dict) -> dict | None:
        query = _build_query(product)
        url = f"https://www.amazon.com.tr/s?k={query.replace(' ', '+')}"

        logger.debug(f"[amazon] Arama: {query}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self._wait(900)  # 2500ms → 900ms (resim yok, daha hızlı)

            cards = await self.page.locator(
                "[data-component-type='s-search-result'][data-asin]:not([data-asin=''])"
            ).all()

            if not cards:
                logger.warning(f"[amazon] Sonuç yok: {query}")
                return None

            best_score, best = 0, None
            for card in cards[:8]:
                try:
                    title_el = card.locator("h2 span")
                    if await title_el.count() == 0:
                        continue
                    title = (await title_el.first.inner_text()).strip()

                    whole_el = card.locator(".a-price-whole")
                    frac_el = card.locator(".a-price-fraction")
                    if await whole_el.count() == 0:
                        continue
                    whole = re.sub(r"[^\d]", "", await whole_el.first.inner_text())
                    frac = re.sub(r"[^\d]", "", await frac_el.first.inner_text()) if await frac_el.count() > 0 else "00"
                    if not whole:
                        continue
                    price = float(f"{whole}.{frac[:2]}")

                    link_el = card.locator("h2 a").first
                    href = await link_el.get_attribute("href") if await link_el.count() > 0 else ""
                    full_url = href if href.startswith("http") else f"https://www.amazon.com.tr{href}"

                    in_stock = await card.locator(".a-color-error, [class*='unavailable']").count() == 0

                    score = self.score_match(title, product)
                    logger.debug(f"  score={score:3d} | {price:>9.2f} TL | {title[:55]}")
                    if score > best_score:
                        best_score = score
                        best = {"title": title, "url": full_url, "price": price, "in_stock": in_stock}

                except Exception:
                    continue

            if best and best_score >= 40:
                logger.info(f"[amazon] {best['price']:.2f} TL  score={best_score}  {best['title'][:50]}")
                return best

            logger.warning(f"[amazon] Zayıf eşleşme (score={best_score}): {query}")
            return None

        except Exception as e:
            logger.error(f"[amazon] Hata: {e}")
            await self._screenshot(f"error_{product['product_id']}")
            return None


def _build_query(p: dict) -> str:
    parts = [p["brand"], p["model"]]
    if p.get("variant"):
        parts.append(p["variant"])
    return " ".join(x for x in parts if x)
