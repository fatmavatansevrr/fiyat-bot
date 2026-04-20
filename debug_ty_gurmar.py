import asyncio, sys
from playwright.async_api import async_playwright
sys.stdout.reconfigure(encoding='utf-8')

async def trendyol():
    print("\n===== TRENDYOL card internals =====")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="tr-TR", viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 Chrome/124.0.0.0")
        page = await ctx.new_page()
        await page.goto("https://www.trendyol.com/sr?q=Pril+bulaşık", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        card = page.locator("[data-testid='product-card']").first
        # Get full HTML
        html = await card.inner_html()
        print(f"Full card HTML:\n{html[:3000]}")
        print("\n--- Testing selectors inside card ---")
        for sel in ["[class*='name']","[class*='product-name']","[class*='prdct']","[class*='desc']","[class*='card-name']","span[class*='name']","div[class*='name']","h3","h4","[class*='title']"]:
            try:
                el = card.locator(sel)
                count = await el.count()
                if count > 0:
                    texts = []
                    for i in range(min(count, 3)):
                        t = await el.nth(i).inner_text()
                        if t.strip():
                            texts.append(repr(t.strip()[:50]))
                    if texts:
                        print(f"  OK {sel!r:40s} -> {', '.join(texts)}")
            except: pass
        await browser.close()

async def gurmar():
    print("\n===== GURMAR .product-text count =====")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="tr-TR", viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 Chrome/124.0.0.0")
        page = await ctx.new_page()
        await page.goto("https://www.gurmar.com.tr/arama?q=Pril", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        count = await page.locator(".product-text").count()
        print(f".product-text count: {count}")
        if count > 0:
            card = page.locator(".product-text").first
            print(f"HTML:\n{await card.inner_html()}")
        else:
            # Try other selectors
            for sel in ["[class*='product-text']","[class*='product-title']","h4","[class*='card']","a[href*='-p']"]:
                c = await page.locator(sel).count()
                if c > 0: print(f"  {sel!r} -> {c}")
        await browser.close()

async def main():
    await trendyol()
    await gurmar()

asyncio.run(main())
