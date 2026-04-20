"""
Playwright tabanlı adapter temel sınıfı (Amazon ve CarrefourSA için).

Performans iyileştirmeleri:
  - Resim, font, CSS, medya engelleme → sayfa yükü %60-80 daha hızlı
  - concurrency=1: Playwright adaptörleri tek sayfa kullanır, sıralı çalışır
  - Playwright adaptörleri tüm marketi paralel çalışabilir (ayrı tarayıcı örnekleri)
"""
from __future__ import annotations
from abc import ABC, abstractmethod

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from src.utils.logger import logger
from config.settings import LOGS_DIR

# Bu kaynak tipleri engellenir → sayfa daha hızlı yüklenir
_BLOCKED_TYPES = {"image", "media", "font", "stylesheet"}


class BaseAdapter(ABC):
    retailer: str = ""
    base_url: str = ""
    concurrency: int = 1  # Playwright adaptörü tek sayfa; orchestrator bunu okur

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None
        self.region_set: bool = False

    async def __aenter__(self):
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--lang=tr-TR", "--disable-images", "--blink-settings=imagesEnabled=false"],
        )
        self._context = await self._browser.new_context(
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        self.page = await self._context.new_page()

        # Gereksiz kaynakları engelle → %60-80 daha hızlı yükleme
        await self.page.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.resource_type in _BLOCKED_TYPES
                else route.continue_()
            ),
        )
        return self

    async def __aexit__(self, *_):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _screenshot(self, name: str):
        path = LOGS_DIR / f"{self.retailer}_{name}.png"
        try:
            await self.page.screenshot(path=str(path), full_page=False)
            logger.debug(f"Screenshot → {path.name}")
        except Exception:
            pass

    async def _slow_type(self, selector: str, text: str, delay: int = 70):
        await self.page.click(selector)
        await self.page.fill(selector, "")
        await self.page.type(selector, text, delay=delay)

    async def _wait(self, ms: int = 1500):
        await self.page.wait_for_timeout(ms)

    async def _accept_cookies(self):
        try:
            await self.page.click(
                # Genel OnetTrust / site-agnostik çerez kabul butonları
                "button#onetrust-accept-btn-handler, "
                "[id*='cookie'] button[class*='accept'], "
                "[class*='cookie'] button[class*='accept'], "
                "button[class*='cookie-accept'], "
                # CarrefourSA özel çerez butonu
                "button#accept, "
                # Ek yaygın pattern'ler
                "button[id*='accept-all'], "
                "button[class*='accept-all']",
                timeout=4000,
            )
            await self._wait(600)
        except Exception:
            pass

    # ── Interface ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def ensure_region(self) -> bool:
        """Set delivery city/store to Izmir. Called once before product loop."""

    @abstractmethod
    async def search_product(self, product: dict) -> dict | None:
        """
        Search and return best match or None.
        Result must contain: title, url, price (float), in_stock (bool)
        """

    # ── Scoring helper shared by all adapters ─────────────────────────────────

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
    """Türkçe → ASCII dönüşümü + küçük harf. Karakter eşleşmesini güvenilir kılar."""
    return (
        s.lower()
        .replace("ü", "u").replace("ş", "s").replace("ı", "i")
        .replace("ğ", "g").replace("ç", "c").replace("ö", "o")
        .replace("â", "a").replace("î", "i").replace("û", "u")
    )
