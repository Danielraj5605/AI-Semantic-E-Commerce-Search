"""Populate categories.parent_category_id so the class tree has real subclass edges.

Idempotent: parents are created if missing, children are re-pointed to them, and
re-running changes nothing. Works against whichever database settings point at
(Neon/Postgres or the local SQLite file).

    python scripts/set_category_hierarchy.py            # apply
    python scripts/set_category_hierarchy.py --dry-run  # show the plan only
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.models import Category

# parent -> children. Parents that are not already categories are created.
HIERARCHY = {
    "Electronics": ["Laptops", "Smartphones", "Audio"],
    "Clothing": ["Men's Clothing", "Women's Clothing", "Footwear"],
    "Home & Living": ["Home & Kitchen", "Pet Supplies", "Office"],
}


def apply(session: Session, dry_run: bool = False) -> list[str]:
    log: list[str] = []
    by_name = {c.name: c for c in session.scalars(select(Category))}

    for parent_name, children in HIERARCHY.items():
        parent = by_name.get(parent_name)
        if parent is None:
            log.append(f"create  {parent_name}")
            if dry_run:
                log += [f"link    {c} -> {parent_name}" for c in children if c in by_name]
                continue
            parent = Category(name=parent_name)
            session.add(parent)
            session.flush()
            by_name[parent_name] = parent

        for child_name in children:
            child = by_name.get(child_name)
            if child is None:
                log.append(f"MISSING {child_name} (skipped)")
                continue
            if dry_run:
                if child.parent_category_id is None:
                    log.append(f"link    {child_name} -> {parent_name}")
            elif child.parent_category_id != parent.category_id:
                child.parent_category_id = parent.category_id
                log.append(f"link    {child_name} -> {parent_name}")

    if not dry_run:
        session.commit()
    return log


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    engine = create_engine(get_settings().database_url_sync)
    with Session(engine) as s:
        actions = apply(s, dry_run=dry)
    print("\n".join(actions) if actions else "Hierarchy already up to date.")
    engine.dispose()
