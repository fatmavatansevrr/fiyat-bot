"""
Trendyol adapter — tarayıcısız, HTTP tabanlı.

Strateji 1 (birincil): Public arama API'si
  https://public.trendyol.com/discovery-web-searchgw-service/api/filter/search/v2
  → JSON cevap, 10-50 KB, <1 sn

Strateji 2 (yedek): HTML'deki __NEXT_DATA__ JSON bloğu
  Trendyol Next.js kullanır; ilk render verisi sayfaya gömülü gelir,
  tarayıcı açmaya gerek yok.

Strateji 3 (son yedek): selectolax ile doğrudan HTML CSS selector taraması
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote_plus

from selectolax.parser import HTMLParser

from src.adapters.http_base import HTTPAdapter
from src.utils.logger import logger

_API_URL = "https://public.trendyol.com/discovery-web-searchgw-service/api/filter/search/v2"
_SEARCH_URL = "https://www.trendyol.com/sr"


class TrendyolAdapter(HTTPAdapter):
    retailer = "trendyol"
    base_url = "https://www.trendyol.com"

    async def ensure_region(self) -> bool:
        return True  # Trendyol halka açık fiyatlar için bölge gerektirmiyor

    async def search_product(self, product: dict) -> dict | None:
        query = _build_query(product)

        # — Strateji 1: Public API —
        result = await self._try_api(product, query)
        if result:
            return result

        # — Strateji 2: __NEXT_DATA__ —
        result = await self._try_next_data(product, query)
        if result:
            return result

        # — Strateji 3: selectolax CSS —
        return await self._try_html_css(product, query)

    # ── Strateji 1 ─────────────────────────────────────────────────────────────

    async def _try_api(self, product: dict, query: str) -> dict | None:
        params = {
            "q": query,
            "pi": 1,
            "culture": "tr-TR",
            "userGenderId": 1,
            "pId": 1,
            "scoringAlgorithmId": 2,
            "categoryRelevancyEnabled": "false",
            "isLegalRequirement": "false",
        }
        headers = self._json_headers({
            "Referer": "https://www.trendyol.com/",
            "Origin": "https://www.trendyol.com",
        })

        data = await self._get_json(_API_URL, params=params, headers=headers)
        if not data:
            return None

        # API'nin birden fazla olası yapısını destekle
        items = (
            _dig(data, "result", "products")
            or _dig(data, "products")
            or _dig(data, "data", "products")
            or []
        )
        if not items:
            logger.debug(f"[trendyol/api] Sonuç yok: {query}")
            return None

        best_score, best = 0, None
        for item in items[:8]:
            title = item.get("name") or item.get("title") or ""
            if not title:
                continue

            price = (
                _dig(item, "price", "sellingPrice")
                or _dig(item, "price", "discountedPrice")
                or _dig(item, "price", "originalPrice")
                or item.get("price")
                or item.get("sellingPrice")
            )
            if price is None:
                continue

            url_path = item.get("url") or item.get("productUrl") or ""
            full_url = (
                url_path if url_path.startswith("http")
                else f"https://www.trendyol.com{url_path}"
            )
            in_stock = not item.get("soldOut", False)

            score = self.score_match(title, product)
            logger.debug(f"  [api] {score:3d} | {float(price):>9.2f} TL | {title[:55]}")
            if score > best_score:
                best_score = score
                best = {"title": title, "url": full_url,
                        "price": float(price), "in_stock": in_stock}

        if best and best_score >= 40:
            logger.info(f"[trendyol/api] {best['price']:.2f} TL  score={best_score}  {best['title'][:50]}")
            return best

        logger.debug(f"[trendyol/api] Zayıf eşleşme (score={best_score}): {query}")
        return None

    # ── Strateji 2 ─────────────────────────────────────────────────────────────

    async def _try_next_data(self, product: dict, query: str) -> dict | None:
        url = f"{_SEARCH_URL}?q={quote_plus(query)}&os=1"
        resp = await self._get(url, headers=self._headers({"Referer": "https://www.trendyol.com/"}))
        if not resp:
            return None

        tree = HTMLParser(resp.text)
        script = tree.css_first("script#__NEXT_DATA__")
        if not script:
            return None

        try:
            data = json.loads(script.text())
        except Exception:
            return None

        # Trendyol Next.js props ağacında ürünlere birden fazla yoldan ulaşılabilir
        page_props = _dig(data, "props", "pageProps") or {}
        items = (
            _dig(page_props, "search", "result", "products")
            or _dig(page_props, "initialSearch", "result", "products")
            or _dig(page_props, "products")
            or []
        )
        if not items:
            return None

        best_score, best = 0, None
        for item in items[:8]:
            title = item.get("name") or item.get("title") or ""
            price = (
                _dig(item, "price", "sellingPrice")
                or _dig(item, "price", "discountedPrice")
                or item.get("price")
            )
            if not title or price is None:
                continue

            url_path = item.get("url") or ""
            full_url = url_path if url_path.startswith("http") else f"https://www.trendyol.com{url_path}"
            in_stock = not item.get("soldOut", False)

            score = self.score_match(title, product)
            logger.debug(f"  [next] {score:3d} | {float(price):>9.2f} TL | {title[:55]}")
            if score > best_score:
                best_score = score
                best = {"title": title, "url": full_url,
                        "price": float(price), "in_stock": in_stock}

        if best and best_score >= 40:
            logger.info(f"[trendyol/next] {best['price']:.2f} TL  score={best_score}  {best['title'][:50]}")
            return best
        return None

    # ── Strateji 3 ─────────────────────────────────────────────────────────────

    async def _try_html_css(self, product: dict, query: str) -> dict | None:
        url = f"{_SEARCH_URL}?q={quote_plus(query)}&os=1"
        resp = await self._get(url, headers=self._headers({"Referer": "https://www.trendyol.com/"}))
        if not resp:
            return None

        tree = HTMLParser(resp.text)

        # Birden fazla olası kart seçici dene
        cards = (
            tree.css("[data-testid='product-card']")
            or tree.css(".product-card")
            or tree.css(".p-card-wrppr")
        )
        if not cards:
            logger.warning(f"[trendyol/html] Sonuç yok: {query}")
            return None

        best_score, best = 0, None
        for card in cards[:8]:
            title_el = card.css_first("h2.title") or card.css_first(".prdct-desc-cntnr-name")
            if not title_el:
                continue
            title = title_el.text(strip=True).replace("\n", " ")

            price_el = (
                card.css_first("[class*='price-item']")
                or card.css_first("[class*='prc-box-dscntd']")
                or card.css_first("[class*='price']")
            )
            if not price_el:
                continue
            price = _parse_price(price_el.text(strip=True).split("\n")[0])
            if price is None:
                continue

            link_el = card.css_first("a[href*='-p-']") or card.css_first("a[href]")
            href = link_el.attributes.get("href", "") if link_el else ""
            full_url = href if href.startswith("http") else f"https://www.trendyol.com{href}"

            in_stock = not bool(card.css_first("[class*='out-of-stock']"))

            score = self.score_match(title, product)
            logger.debug(f"  [html] {score:3d} | {price:>9.2f} TL | {title[:55]}")
            if score > best_score:
                best_score = score
                best = {"title": title, "url": full_url,
                        "price": price, "in_stock": in_stock}

        if best and best_score >= 40:
            logger.info(f"[trendyol/html] {best['price']:.2f} TL  score={best_score}  {best['title'][:50]}")
            return best

        logger.warning(f"[trendyol] Hiçbir strateji eşleşme bulamadı: {query}")
        return None


# ── Yardımcılar ────────────────────────────────────────────────────────────────

def _build_query(p: dict) -> str:
    return " ".join(x for x in [p["brand"], p["model"], p.get("variant")] if x)


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d,]", "", text.strip()).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _dig(obj: dict, *keys):
    """Güvenli iç içe dict erişimi: _dig(d, 'a', 'b', 'c') → d['a']['b']['c']"""
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
        if obj is None:
            return None
    return obj
