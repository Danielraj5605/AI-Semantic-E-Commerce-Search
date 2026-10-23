"""Replace the product images whose original Unsplash links were deleted (404).

Each entry names a product and a freely licensed photo (Unsplash License: free to
use, attribution appreciated but not required). Photographers are credited here.
Photos were picked by eye, not just by keyword: an earlier candidate "hair dryer"
turned out to be a perfume bottle.

Idempotent. Only the products listed below are touched.

    python scripts/set_product_images.py --dry-run
    python scripts/set_product_images.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.models import Product

U = "https://images.unsplash.com/"

# product name -> (image URL, photographer)
IMAGES = {
    "Insulated Men's Parka": (U + "photo-1516647221-2087c5f12608?w=400", "Al Elmes"),
    "Merino Wool Crew Sweater": (U + "photo-1611312449297-a69dc9c3987b?w=400", "Caio Coelho"),
    "Cashmere Blend Cardigan": (U + "photo-1579206464424-7e43a81cadc1?w=400", "lilartsy"),
    "TrueWireless Earbuds Sport": (U + "photo-1756902368926-eb9e5e9d2a69?w=400", "Invisible"),
    "Robot Vacuum with Mapping": (U + "photo-1653990480360-31a12ce9723e?w=400", "Onur Binay"),
    "Professional Hair Dryer 1875W": (U + "photo-1727364438136-6edc10ef0a52?w=400", "Shubham Dhage"),
    "Electric Toothbrush Sonic": (U + "photo-1593010997923-65947b08b772?w=400", "Stephen Crowther"),
}


def main(dry_run: bool) -> None:
    engine = create_engine(get_settings().database_url_sync)
    with Session(engine) as session:
        for name, (url, credit) in IMAGES.items():
            product = session.scalar(select(Product).where(Product.name == name))
            if product is None:
                print(f"  missing product (skipped): {name}")
            elif product.image_url == url:
                print(f"  already set: {name}")
            else:
                print(f"  {'would set' if dry_run else 'setting'}: {name}  ({credit})")
                if not dry_run:
                    product.image_url = url
        if not dry_run:
            session.commit()
    engine.dispose()


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
