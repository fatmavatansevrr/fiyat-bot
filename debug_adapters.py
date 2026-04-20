"""
Her adapter için tek ürünle test — HTML dump + screenshot alır.
"""
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

LOGS = Path("logs")
LOGS.mkdir(exist_ok=True)

TEST_PRODUCT = {
    "product_id": "001",
    "brand": "Pril",
    "model": "Sıvı Bulaşık Deterjanı",
    "variant": "1350g",
    "keywords": "Hijyen Soğuk Suda Etkili",
    "barcode_ean": "",
    "discount_threshold": 25,
}

SEARCHES = {
    "trendyol":  "https://www.trendyol.com/sr?q=Pril+bulaşık",
    "migros":    "https://www.migros.com.tr/arama?q=Pril",
    "carrefour": "https://www.carrefoursa.com/search?text=Pril",
    "gurmar":    "https://www.gurmar.com.tr/arama?q=Pril",
}

async def check(name, url):
    print(f"\n{'='*50}\n{name.upper()}: {url}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            locale="tr-TR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Screenshot
        ss = LOGS / f"debug_{name}.png"
        await page.screenshot(path=str(ss), full_page=False)
        print(f"  Screenshot: {ss}")

        # Try common card selectors and report counts
        selectors = [
            "[data-testid='product-card']",
            ".p-card-wrppr",
            ".product-card",
            "[class*='product-card']",
            "[class*='product-item']",
            "[class*='ProductCard']",
            "sm-product-card",
            ".grid-item",
            "[class*='urun']",
            "li[class*='product']",
        ]
        for sel in selectors:
            count = await page.locator(sel).count()
            if count > 0:
                print(f"  OK {sel!r:45s} -> {count} elements")

        # Print first 300 chars of body text to see page structure
        body = await page.locator("body").inner_text()
        print(f"  Page text preview: {body[:200].strip()!r}")

        await browser.close()

async def main():
    for name, url in SEARCHES.items():
        await check(name, url)

asyncio.run(main())
