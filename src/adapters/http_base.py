"""
Base class for HTTP-based (no-browser) adapters.

Playwright yerine httpx.AsyncClient + selectolax kullanır:
- Tarayıcı başlatma yükü yok (~3-5 sn kazanç per market)
- Resim/CSS/JS indirilmiyor → sayfa başına sadece HTML gelir (~10-50 KB)
- concurrency=5: aynı anda 5 ürün taranır

Seçici kullanım: Trendyol, Migros, Gürmar bu sınıftan türer.
Amazon ve CarrefourSA hâlâ Playwright kullanır (JS rendering gerektiriyor).
"""
from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod

import httpx

from src.utils.logger import logger

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


class HTTPAdapter(ABC):
    retailer: str = ""
    base_url: str = ""
    concurrency: int = 5  # orchestrator bu değeri okuyarak Semaphore oluşturur

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=8.0, read=18.0, write=8.0, pool=5.0),
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=12,
                max_keepalive_connections=6,
                keepalive_expiry=30,
            ),
        )
        return self

    async def __aexit__(self, *_):
        if self._client:
            await self._client.aclose()

    def _headers(self, extra: dict | None = None) -> dict[str, str]:
        h = {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        }
        if extra:
            h.update(extra)
        return h

    def _json_headers(self, extra: dict | None = None) -> dict[str, str]:
        h = self._headers()
        h["Accept"] = "application/json, text/plain, */*"
        h["Sec-Fetch-Dest"] = "empty"
        h["Sec-Fetch-Mode"] = "cors"
        if extra:
            h.update(extra)
        return h

    async def _get(self, url: str, *, params: dict | None = None,
                   headers: dict | None = None) -> httpx.Response | None:
        try:
            resp = await self._client.get(url, params=params,
                                          headers=headers or self._headers())
            if resp.status_code == 200:
                return resp
            logger.debug(f"[{self.retailer}] HTTP {resp.status_code}: {url[:80]}")
            return None
        except Exception as e:
            logger.debug(f"[{self.retailer}] GET error: {e}")
            return None

    async def _get_json(self, url: str, *, params: dict | None = None,
                        headers: dict | None = None) -> dict | list | None:
        resp = await self._get(url, params=params,
                               headers=headers or self._json_headers())
        if resp is None:
            return None
        try:
            return resp.json()
        except Exception as e:
            logger.debug(f"[{self.retailer}] JSON parse error: {e}")
            return None

    @abstractmethod
    async def ensure_region(self) -> bool: ...

    @abstractmethod
    async def search_product(self, product: dict) -> dict | None: ...

    @staticmethod
    def score_match(title: str, product: dict) -> int:
        # Türkçe karakterleri normalize et: Ülker==Ulker, Çikolata==Cikolata
        t = _tr_norm(title)
        score = 0
        if _tr_norm(product["brand"]) in t:
            score += 40
        if _tr_norm(product["model"]) in t:
            score += 40
        if product.get("variant") and _tr_norm(product["variant"]) in t:
            score += 15
        if product.get("keywords"):
            for kw in _tr_norm(product["keywords"]).split():
                if kw in t:
                    score += 3
        return score


def _tr_norm(s: str) -> str:
    """Türkçe → ASCII dönüşümü + küçük harf."""
    return (
        s.lower()
        .replace("ü", "u").replace("ş", "s").replace("ı", "i")
        .replace("ğ", "g").replace("ç", "c").replace("ö", "o")
        .replace("â", "a").replace("î", "i").replace("û", "u")
    )
