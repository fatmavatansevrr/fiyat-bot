import asyncio, sys
from playwright.async_api import async_playwright

async def check(name, url, card_sel):
    sys.stdout.reconfigure(encoding='utf-8')
    print(f"\n{'='*55}\n{name.upper()} -- card: {card_sel!r}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="tr-TR", viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36")
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        for sel in ["button#onetrust-accept-btn-handler","button.kabul","[id*='accept']","button[class*='accept']"]:
            try: await page.click(sel, timeout=1500); break
            except: pass
        await page.wait_for_timeout(1500)

        cards = await page.locator(card_sel).all()
        print(f"  Cards: {len(cards)}")
        if cards:
            card = cards[0]
            html = await card.inner_html()
            print(f"  HTML:\n{html[:1200]}\n")
        await browser.close()

async def main():
    # Migros — try fe-product-card
    await check("migros", "https://www.migros.com.tr/arama?q=Pril", "fe-product-card")
    # Gurmar — try product card selectors
    await check("gurmar", "https://www.gurmar.com.tr/arama?q=Pril", ".product-list .ant-card, [class*='product-list'] .ant-card-body, .ant-list-item")
    # Carrefour — check price in card html
    await check("carrefour", "https://www.carrefoursa.com/search?text=Pril", ".product-card")

asyncio.run(main())
