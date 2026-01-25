#!/usr/bin/env python3
"""Test script for the auto-fix scraper workflow.

Usage:
    python3 scripts/test_auto_fix.py --break control
    # Then run Amp manually to test the fix flow
    python3 scripts/test_auto_fix.py --restore control
"""

import argparse
import re
import shutil
from pathlib import Path

SCRAPERS_DIR = Path(__file__).parent.parent / "scrapers"
BACKUP_SUFFIX = ".backup"


def find_scraper(name: str) -> Path | None:
    """Find a scraper by name across all categories."""
    for category in ["music", "theatre", "culture"]:
        scraper_path = SCRAPERS_DIR / category / f"{name}.py"
        if scraper_path.exists():
            return scraper_path
    return None


def break_scraper(name: str) -> None:
    """Intentionally break a scraper by changing its CSS selectors."""
    scraper_path = find_scraper(name)
    if not scraper_path:
        print(f"❌ Scraper '{name}' not found")
        return

    # Backup original
    backup_path = scraper_path.with_suffix(scraper_path.suffix + BACKUP_SUFFIX)
    if backup_path.exists():
        print(f"⚠️  Backup already exists at {backup_path}")
        print("   Run --restore first or delete the backup manually")
        return

    shutil.copy(scraper_path, backup_path)
    print(f"✅ Backed up to {backup_path}")

    # Read and modify the scraper
    content = scraper_path.read_text()

    # Find CSS selectors and break them
    # Look for soup.select("...") or soup.select_one("...")
    modified = re.sub(
        r'\.select\("([^"]+)"\)',
        r'.select("BROKEN_SELECTOR_\1")',
        content,
    )
    modified = re.sub(
        r"\.select\('([^']+)'\)",
        r".select('BROKEN_SELECTOR_\1')",
        modified,
    )
    modified = re.sub(
        r'\.select_one\("([^"]+)"\)',
        r'.select_one("BROKEN_SELECTOR_\1")',
        modified,
    )
    modified = re.sub(
        r"\.select_one\('([^']+)'\)",
        r".select_one('BROKEN_SELECTOR_\1')",
        modified,
    )

    if modified == content:
        print("⚠️  No selectors found to break - trying alternative approach")
        # Try breaking the EVENTS_URL instead
        modified = re.sub(
            r'EVENTS_URL = "([^"]+)"',
            r'EVENTS_URL = "https://broken-url-for-testing.invalid/"',
            content,
        )

    scraper_path.write_text(modified)
    print(f"✅ Broke scraper at {scraper_path}")
    print("\nNow test with:")
    print(f'  python3 -c "from scrapers.{scraper_path.parent.name}.{name} import scrape; print(scrape())"')


def restore_scraper(name: str) -> None:
    """Restore a scraper from its backup."""
    scraper_path = find_scraper(name)
    if not scraper_path:
        # Try to find backup
        for category in ["music", "theatre", "culture"]:
            backup_path = SCRAPERS_DIR / category / f"{name}.py{BACKUP_SUFFIX}"
            if backup_path.exists():
                scraper_path = SCRAPERS_DIR / category / f"{name}.py"
                break

    if not scraper_path:
        print(f"❌ Scraper '{name}' not found")
        return

    backup_path = scraper_path.with_suffix(scraper_path.suffix + BACKUP_SUFFIX)
    if not backup_path.exists():
        print(f"❌ No backup found at {backup_path}")
        return

    shutil.move(backup_path, scraper_path)
    print(f"✅ Restored scraper from {backup_path}")


def list_scrapers() -> None:
    """List all available scrapers."""
    print("Available scrapers:")
    for category in ["music", "theatre", "culture"]:
        category_dir = SCRAPERS_DIR / category
        if category_dir.exists():
            scrapers = [f.stem for f in category_dir.glob("*.py") if f.stem != "__init__"]
            if scrapers:
                print(f"\n  {category}:")
                for s in sorted(scrapers):
                    backup = (category_dir / f"{s}.py{BACKUP_SUFFIX}").exists()
                    status = " (broken - backup exists)" if backup else ""
                    print(f"    - {s}{status}")


def main():
    parser = argparse.ArgumentParser(description="Test auto-fix scraper workflow")
    parser.add_argument("--break", dest="break_scraper", metavar="NAME", help="Break a scraper")
    parser.add_argument("--restore", metavar="NAME", help="Restore a scraper from backup")
    parser.add_argument("--list", action="store_true", help="List available scrapers")

    args = parser.parse_args()

    if args.list:
        list_scrapers()
    elif args.break_scraper:
        break_scraper(args.break_scraper)
    elif args.restore:
        restore_scraper(args.restore)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
