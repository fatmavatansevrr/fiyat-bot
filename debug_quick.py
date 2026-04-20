import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')

from src.storage.database import init_db
from src.storage.product_source import load_inventory

TEST_PRODUCT = {
    "product_id": "001", "brand": "Pril",
    "model": "Sıvı Bulaşık Deterjanı", "variant": "1350g",
    "keywords": "Hijyen Soğuk Suda Etkili", "barcode_ean": "",
    "discount_threshold": 25,
}

async def test(adapter_cls, name):
    print(f"\n--- {name.upper()} ---")
    try:
        async with adapter_cls(headless=True) as a:
            result = await a.search_product(TEST_PRODUCT)
            if result:
                print(f"  FOUND: {result['price']:.2f} TL | {result['title'][:60]}")
            else:
                print(f"  NO MATCH")
    except Exception as e:
        print(f"  ERROR: {e}")

async def main():
    init_db()
    from src.adapters.trendyol import TrendyolAdapter
    from src.adapters.migros import MigrosAdapter
    from src.adapters.carrefour import CarrefourAdapter
    from src.adapters.gurmar import GurmarAdapter

    await test(TrendyolAdapter, "trendyol")
    await test(MigrosAdapter, "migros")
    await test(CarrefourAdapter, "carrefour")
    await test(GurmarAdapter, "gurmar")

asyncio.run(main())
