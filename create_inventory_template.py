"""
Run once to create the inventory template: python create_inventory_template.py
Then open data/inventory.xlsx and fill in your own products.
"""
import pandas as pd
from pathlib import Path

Path("data").mkdir(exist_ok=True)

sample = [
    {
        "product_id": "001",
        "brand": "Omo",
        "model": "Matik Color",
        "variant": "5 kg",
        "barcode_ean": "",
        "keywords": "toz deterjan renkliler",
        "baseline_price": "",
        "discount_threshold": 25,
        "active": 1,
    },
    {
        "product_id": "002",
        "brand": "Ariel",
        "model": "Dağ Esintisi",
        "variant": "4 kg",
        "barcode_ean": "",
        "keywords": "toz deterjan",
        "baseline_price": "",
        "discount_threshold": 20,
        "active": 1,
    },
    {
        "product_id": "003",
        "brand": "Nestle",
        "model": "Nescafe Classic",
        "variant": "200g",
        "barcode_ean": "",
        "keywords": "kahve hazır",
        "baseline_price": "",
        "discount_threshold": 25,
        "active": 1,
    },
]

df = pd.DataFrame(sample)
out = Path("data/inventory.xlsx")
df.to_excel(out, index=False)
print(f"Template created: {out}")
print("Open it in Excel, replace the sample rows with your products, save and close.")
