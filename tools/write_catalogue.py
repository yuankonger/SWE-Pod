"""Writes Core's starting catalogue (services/core/src/catalogue.json).

The shape follows Saleor's sample data (saleor/static/populatedb_data.json: 29 products, 81 variants, nested
categories, product types, half the products with one variant and a few with many, some variants with no SKU,
prices from about 2 to over 2,000). The products themselves are SeedCo's own. Ids are stable: the first three
products are the ones the company has always sold.
Usage: python3 tools/write_catalogue.py .
"""
import json
import os
import sys

CATEGORIES = [  # (slug, name, parent slug)
    ("boxes", "Boxes", None), ("tea", "Tea", None), ("black-tea", "Black tea", "tea"), ("green-tea", "Green tea", "tea"),
    ("herbal-tea", "Herbal tea", "tea"), ("coffee", "Coffee", None), ("whole-bean", "Whole bean", "coffee"),
    ("ground", "Ground", "coffee"), ("pantry", "Pantry", None), ("honey-and-jam", "Honey & jam", "pantry"),
    ("biscuits", "Biscuits", "pantry"), ("teaware", "Teaware", None), ("pots", "Pots", "teaware"), ("cups", "Cups", "teaware"),
    ("brewing", "Brewing", None), ("gifts", "Gifts", None), ("gift-cards", "Gift cards", "gifts"),
]
TYPES = ["Subscription box", "Add-on", "Loose tea", "Coffee", "Pantry item", "Teaware", "Equipment", "Gift card"]

# (name, category, type, [(variant name, sku or None, price)])
PRODUCTS = [
    ("Small monthly box", "boxes", "Subscription box", [("", "BOX-S", "24.99")]),
    ("Large monthly box", "boxes", "Subscription box", [("", "BOX-L", "39.50")]),
    ("Tea add-on", "tea", "Add-on", [("", "ADD-TEA", "6.25")]),
    ("Assam Breakfast", "black-tea", "Loose tea", [("50 g", "TEA-ASM-50", "7.50"), ("100 g", "TEA-ASM-100", "13.00"), ("250 g", "TEA-ASM-250", "28.00"),
                                                    ("500 g", "TEA-ASM-500", "49.00"), ("1 kg", "TEA-ASM-1000", "89.00")]),
    ("Earl Grey Crème", "black-tea", "Loose tea", [("50 g", "TEA-EGC-50", "8.25"), ("100 g", "TEA-EGC-100", "14.50"), ("250 g", "TEA-EGC-250", "31.00")]),
    ("Darjeeling First Flush", "black-tea", "Loose tea", [("50 g", "TEA-DJF-50", "14.00"), ("100 g", "TEA-DJF-100", "26.00")]),
    ("Sencha Fukamushi", "green-tea", "Loose tea", [("50 g", "TEA-SEN-50", "11.00"), ("100 g", "TEA-SEN-100", "19.99"), ("250 g", "TEA-SEN-250", "44.00")]),
    ("Dragon Well (Lóngjǐng)", "green-tea", "Loose tea", [("50 g", "TEA-LJ-50", "16.50"), ("100 g", "TEA-LJ-100", "30.00"), ("250 g", "TEA-LJ-250", "68.00"),
                                                           ("500 g", "TEA-LJ-500", "125.00"), ("1 kg", "TEA-LJ-1000", "230.00")]),
    ("Matcha, ceremonial grade", "green-tea", "Loose tea", [("30 g tin", "TEA-MAT-30", "32.00")]),
    ("Chamomile & Honeybush", "herbal-tea", "Loose tea", [("50 g", "TEA-CHM-50", "6.75"), ("100 g", "TEA-CHM-100", "11.50"), ("250 g", "TEA-CHM-250", "24.00")]),
    ("Rooibos \"Crème Brûlée\"", "herbal-tea", "Loose tea", [("50 g", "TEA-RCB-50", "7.25"), ("100 g", "TEA-RCB-100", "12.50"), ("250 g", "TEA-RCB-250", "26.50"),
                                                               ("500 g", "TEA-RCB-500", "47.00"), ("1 kg", "TEA-RCB-1000", "85.00")]),
    ("Peppermint", "herbal-tea", "Loose tea", [("50 g", "TEA-PEP-50", "5.50")]),
    ("House Espresso", "whole-bean", "Coffee", [("250 g", "COF-ESP-250", "12.00"), ("500 g", "COF-ESP-500", "22.00"), ("1 kg", "COF-ESP-1000", "40.00"),
                                                 ("2.5 kg", "COF-ESP-2500", "92.00"), ("5 kg", "COF-ESP-5000", "175.00")]),
    ("Ethiopia Guji, natural", "whole-bean", "Coffee", [("250 g", "COF-GUJ-250", "16.50"), ("500 g", "COF-GUJ-500", "31.00"), ("1 kg", "COF-GUJ-1000", "58.00")]),
    ("Decaf Colombia", "ground", "Coffee", [("250 g", "COF-DEC-250", "13.50"), ("500 g", "COF-DEC-500", "25.00")]),
    ("Filter blend", "ground", "Coffee", [
        ("250 g, fine", "COF-FIL-250-F", "11.00"), ("250 g, medium", "COF-FIL-250-M", "11.00"), ("250 g, coarse", "COF-FIL-250-C", "11.00"),
        ("500 g, fine", "COF-FIL-500-F", "20.00"), ("500 g, medium", "COF-FIL-500-M", "20.00"), ("500 g, coarse", "COF-FIL-500-C", "20.00"),
        ("1 kg, fine", "COF-FIL-1000-F", "37.00"), ("1 kg, medium", "COF-FIL-1000-M", "37.00"), ("1 kg, coarse", "COF-FIL-1000-C", "37.00"),
        ("2.5 kg, medium", "COF-FIL-2500-M", "85.00")]),
    ("Beekeeper's wildflower honey", "honey-and-jam", "Pantry item", [("227 g jar", "PAN-HON-227", "9.50")]),
    ("Seville orange marmalade", "honey-and-jam", "Pantry item", [("340 g jar", "PAN-MAR-340", "6.99")]),
    ("Shortbread fingers", "biscuits", "Pantry item", [("Tin of 12", "PAN-SHB-12", "8.50"), ("Tin of 24", "PAN-SHB-24", "15.00"), ("Refill bag", None, "5.00"),
                                                        ("Case of 6 tins", "PAN-SHB-CASE", "45.00")]),
    ("Stem ginger biscuits", "biscuits", "Pantry item", [("Box", "PAN-GIN-1", "4.75")]),
    ("Sugar sticks", "pantry", "Pantry item", [("Pack of 20", "PAN-SUG-20", "1.99")]),
    ("Cast-iron teapot \"Tetsubin\"", "pots", "Teaware", [("0.6 l", "WARE-TET-06", "64.00"), ("0.9 l", "WARE-TET-09", "79.00"), ("1.2 l", "WARE-TET-12", "98.00")]),
    ("Glass teapot with infuser", "pots", "Teaware", [("1 l", "WARE-GLS-10", "34.00")]),
    ("Stoneware cups", "cups", "Teaware", [("Set of 2", "WARE-CUP-2", "22.00"), ("Set of 4", "WARE-CUP-4", "40.00"), ("Set of 6", "WARE-CUP-6", "57.00"),
                                           ("Single, seconds", None, "6.00"), ("Set of 12", "WARE-CUP-12", "108.00")]),
    ("Double-walled glass mug", "cups", "Teaware", [("350 ml", "WARE-MUG-350", "14.00")]),
    ("Pour-over dripper", "brewing", "Equipment", [("Ceramic", "BREW-DRP-CER", "24.00")]),
    ("Variable-temperature kettle", "brewing", "Equipment", [("1 l", "BREW-KET-10", "129.00")]),
    ("Lever espresso machine \"La Paziente\"", "brewing", "Equipment", [("Chrome", "BREW-LEV-CHR", "2300.00")]),
    ("Gift card", "gift-cards", "Gift card", [("$25", "GIFT-25", "25.00"), ("$50", "GIFT-50", "50.00"), ("$100", "GIFT-100", "100.00"),
                                              ("$150", "GIFT-150", "150.00"), ("$200", "GIFT-200", "200.00"), ("$250", "GIFT-250", "250.00"),
                                              ("$300", "GIFT-300", "300.00"), ("$400", "GIFT-400", "400.00"), ("$500", "GIFT-500", "500.00"),
                                              ("$750", "GIFT-750", "750.00"), ("$1,000", "GIFT-1000", "1000.00")]),
]


def slug(text):
    keep = "".join(c if c.isascii() and c.isalnum() else "-" for c in text.lower())
    return "-".join(p for p in keep.split("-") if p)


categories = [{"id": str(i + 1), "slug": s, "name": n, "parent": p} for i, (s, n, p) in enumerate(CATEGORIES)]
types = [{"id": str(i + 1), "name": n, "slug": slug(n)} for i, n in enumerate(TYPES)]
products, variant_id = [], 0
for i, (name, category, kind, variants) in enumerate(PRODUCTS):
    rows = []
    for variant_name, sku, price in variants:
        variant_id += 1
        rows.append({"id": str(variant_id), "name": variant_name, "sku": sku, "price": price})
    products.append({"id": str(i + 1), "name": name, "slug": slug(name), "category": category, "product_type": slug(kind), "variants": rows})
out = os.path.join(sys.argv[1], "services", "core", "src", "catalogue.json")
json.dump({"categories": categories, "product_types": types, "products": products}, open(out, "w"), indent=1, ensure_ascii=False)
print("{} products, {} variants, {} without a SKU".format(len(products), variant_id, sum(1 for p in products for v in p["variants"] if v["sku"] is None)))
