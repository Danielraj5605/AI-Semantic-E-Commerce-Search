"""Clear product image URLs that no longer resolve, so cards show the placeholder.

A URL is cleared only if the server answers 404 or 410 (the image is definitively
gone). Timeouts, DNS failures and 5xx responses are reported but left alone, so
running this while offline cannot wipe good data. Idempotent.

    python scripts/clear_dead_image_urls.py --dry-run   # report only
    python scripts/clear_dead_image_urls.py             # apply
"""

import concurrent.futures as futures
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.models import Product

GONE = {404, 410}


def probe(url: str) -> str:
    """'ok', 'gone' (definitively missing) or 'unknown' (could not tell)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return "ok" if resp.headers.get("content-type", "").startswith("image") else "unknown"
    except urllib.error.HTTPError as err:
        return "gone" if err.code in GONE else "unknown"
    except Exception:
        return "unknown"


def main(dry_run: bool) -> None:
    engine = create_engine(get_settings().database_url_sync)
    with Session(engine) as session:
        products = session.scalars(select(Product).where(Product.image_url.is_not(None))).all()
        with futures.ThreadPoolExecutor(12) as pool:
            verdicts = list(pool.map(lambda p: probe(p.image_url), products))

        gone = [p for p, v in zip(products, verdicts) if v == "gone"]
        unknown = [p for p, v in zip(products, verdicts) if v == "unknown"]
        print(f"checked {len(products)} | ok {verdicts.count('ok')} | gone {len(gone)} | undetermined {len(unknown)}")
        for p in gone:
            print(f"  {'would clear' if dry_run else 'clearing'}: {p.name}")
            if not dry_run:
                p.image_url = None
        for p in unknown:
            print(f"  left alone (could not verify): {p.name}")
        if not dry_run:
            session.commit()
    engine.dispose()


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
