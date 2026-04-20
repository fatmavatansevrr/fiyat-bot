"""
Her site icin title ve price selektorlerini test eder.
"""
import asyncio, sys
from playwright.async_api import async_playwright

async def check(name, url, card_sel, title_sels, price_sels):
    sys.stdout.reconfigure(encoding='utf-8')
    print(f"\n{'='*55}\n{name.upper()}")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            locale="tr-TR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Accept cookies
        for sel in ["button#onetrust-accept-btn-handler","button.cookie-accept","#CybotCookiebotDialogBodyButtonAccept","button[id*='accept']"]:
            try:
                await page.click(sel, timeout=2000)
                await page.wait_for_timeout(800)
                break
            except:
                pass

        await page.wait_for_timeout(1500)
        cards = await page.locator(card_sel).all()
        print(f"  Cards found: {len(cards)}")
        if not cards:
            print("  NO CARDS — trying scroll")
            await page.evaluate("window.scrollTo(0, 500)")
            await page.wait_for_timeout(2000)
            cards = await page.locator(card_sel).all()
            print(f"  After scroll: {len(cards)}")

        if cards:
            card = cards[0]
            # HTML snippet
            html = await card.inner_html()
            print(f"  Card HTML (first 600 chars):\n  {html[:600]}")

            print("\n  Title selectors:")
            for sel in title_sels:
                try:
                    el = card.locator(sel)
                    count = await el.count()
                    if count > 0:
                        text = await el.first.inner_text()
                        print(f"    OK {sel!r} -> {text[:60]!r}")
                    else:
                        print(f"    -- {sel!r} -> 0 elements")
                except Exception as e:
                    print(f"    ERR {sel!r} -> {e}")

            print("\n  Price selectors:")
            for sel in price_sels:
                try:
                    el = card.locator(sel)
                    count = await el.count()
                    if count > 0:
                        text = await el.first.inner_text()
                        print(f"    OK {sel!r} -> {text[:40]!r}")
                    else:
                        print(f"    -- {sel!r} -> 0 elements")
                except Exception as e:
                    print(f"    ERR {sel!r} -> {e}")

        await browser.close()

async def main():
    await check(
        "trendyol",
        "https://www.trendyol.com/sr?q=Pril+bulaşık",
        "[data-testid='product-card']",
        ["[data-testid='product-card-name']",".prdct-desc-cntnr-name","h3","[class*='name']","[class*='title']","p","span"],
        ["[data-testid='price-current-price']",".prc-box-dscntd",".prc-box-sllng","[class*='price']","span[class*='prc']"],
    )
    await check(
        "migros",
        "https://www.migros.com.tr/arama?q=Pril",
        "sm-product-card, [class*='product-card'], .ems-product-card",
        ["[class*='name']","[class*='title']","h3","h4","p","span[class*='name']"],
        ["[class*='price']:not([class*='old'])", "[class*='selling']","[class*='current']","span[class*='price']","[class*='amount']"],
    )
    await check(
        "carrefour",
        "https://www.carrefoursa.com/search?text=Pril",
        ".product-card, [class*='product-card']",
        ["[class*='product-name']","[class*='name']","h3","h4","p","[class*='title']","[class*='label']"],
        ["[class*='current-price']","[class*='sale-price']","[class*='price']:not([class*='old'])","[class*='amount']"],
    )
    await check(
        "gurmar",
        "https://www.gurmar.com.tr/arama?q=Pril",
        "[class*='product-card'],[class*='product-item'],[class*='ProductCard'],div[class*='card']",
        ["[class*='name']","[class*='title']","h3","h4","p","a[class*='name']","span[class*='name']"],
        ["[class*='price']:not([class*='old'])","[class*='current']","span","[class*='amount']","[class*='fiyat']"],
    )

asyncio.run(main())
