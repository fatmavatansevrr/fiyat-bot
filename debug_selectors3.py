import asyncio, sys
from playwright.async_api import async_playwright

async def migros():
    sys.stdout.reconfigure(encoding='utf-8')
    print("\n===== MIGROS title/price within fe-product-card =====")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="tr-TR", viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 Chrome/124.0.0.0")
        page = await ctx.new_page()
        await page.goto("https://www.migros.com.tr/arama?q=Pril", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        for sel in ["button#onetrust-accept-btn-handler","button.kabul","[id*='accept']"]:
            try: await page.click(sel, timeout=1500); break
            except: pass
        await page.wait_for_timeout(1000)

        card = page.locator("fe-product-card").first
        html = await card.inner_html()
        print(f"Full HTML ({len(html)} chars):\n{html[:2500]}")
        await browser.close()

async def gurmar():
    sys.stdout.reconfigure(encoding='utf-8')
    print("\n===== GURMAR — full body selectors =====")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="tr-TR", viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 Chrome/124.0.0.0")
        page = await ctx.new_page()
        await page.goto("https://www.gurmar.com.tr/arama?q=Pril", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Try many selectors
        for sel in [
            ".product-list-item", "[class*='ProductListItem']", "[class*='product-list-item']",
            ".ant-list-item", "[class*='ant-list-item']",
            "[class*='ProductCard']","[class*='product_card']",
            "a[href*='/urun/']", "a[href*='/product/']",
            "[class*='item-card']","[class*='itemCard']",
            "div[class^='Product']", "div[class*='Product']",
        ]:
            count = await page.locator(sel).count()
            if count > 0:
                print(f"  OK {sel!r} -> {count}")

        # Show body HTML snippet around product area
        html = await page.content()
        # Find where product cards start
        idx = html.find('84,95')
        if idx > 0:
            print(f"\n  HTML around first price:\n{html[max(0,idx-500):idx+300]}")
        else:
            idx = html.find('Pril')
            if idx > 0:
                print(f"\n  HTML around 'Pril':\n{html[max(0,idx-300):idx+500]}")

        await browser.close()

async def carrefour():
    sys.stdout.reconfigure(encoding='utf-8')
    print("\n===== CARREFOUR — price HTML =====")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="tr-TR", viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 Chrome/124.0.0.0")
        page = await ctx.new_page()
        await page.goto("https://www.carrefoursa.com/search?text=Pril", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        card = page.locator(".product-card").first
        html = await card.inner_html()
        print(f"Full card HTML:\n{html}")
        await browser.close()

async def main():
    await migros()
    await gurmar()
    await carrefour()

asyncio.run(main())
