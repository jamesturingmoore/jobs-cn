"""
Scrape job posting data from Chinese recruitment platforms.

Supports multiple platforms:
- BOSS直聘 (zhipin.com)
- 智联招聘 (zhaopin.com)
- 前程无忧 (51job.com)

Usage:
    uv run python scrape.py [occupation_slug]
    uv run python scrape.py --all  # Scrape all occupations

Data saved to: html/{platform}/{slug}.json
"""

import asyncio
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "httpx"], check=True)
    import httpx

try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "beautifulsoup4"], check=True)
    from bs4 import BeautifulSoup

try:
    from dotenv import load_dotenv
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "python-dotenv"], check=True)
    from dotenv import load_dotenv

load_dotenv()

# Output directory
HTML_DIR = Path("html")

# Platform configurations
PLATFORMS = {
    "boss": {
        "name": "BOSS直聘",
        "search_url": "https://www.zhipin.com/web/geek/job",
        "params": lambda q: {"query": q, "city": "100010000"},  # 全国
    },
    "zhilian": {
        "name": "智联招聘",
        "search_url": "https://sou.zhaopin.com/",
        "params": lambda q: {"jl": "全国", "kw": q},
    },
    "51job": {
        "name": "前程无忧",
        "search_url": "https://search.51job.com/",
        "params": lambda q: {"jobarea": "000000", "keyword": q},
    }
}

# Rate limiting
REQUEST_DELAY = 2.0  # seconds between requests


def load_occupations() -> list[dict]:
    """Load occupation list."""
    with open("occupations.json", encoding="utf-8") as f:
        return json.load(f)


async def scrape_platform(
    client: httpx.AsyncClient,
    platform: str,
    query: str,
    slug: str
) -> dict | None:
    """Scrape a single platform for job postings."""
    config = PLATFORMS.get(platform)
    if not config:
        return None

    output_dir = HTML_DIR / platform
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{slug}.json"

    # Check cache (30 days)
    if output_file.exists():
        import time
        age_days = (time.time() - output_file.stat().st_mtime) / 86400
        if age_days < 30:
            print(f"  [CACHE] {platform}: {slug}")
            with open(output_file, encoding="utf-8") as f:
                return json.load(f)

    try:
        url = config["search_url"]
        params = config["params"](query)

        # Add headers to appear more like a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": url,
        }

        print(f"  [FETCH] {platform}: {query}")
        response = await client.get(url, params=params, headers=headers, follow_redirects=True)
        response.raise_for_status()

        data = {
            "platform": platform,
            "query": query,
            "slug": slug,
            "url": str(response.url),
            "html": response.text,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Save to file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return data

    except Exception as e:
        print(f"  [ERROR] {platform}: {e}")
        return None


async def scrape_occupation(
    client: httpx.AsyncClient,
    occupation: dict,
    platforms: list[str] = None
) -> dict:
    """Scrape all platforms for a single occupation."""
    slug = occupation["slug"]
    title = occupation["title"]

    print(f"\nScraping: {title} ({slug})")

    results = {}
    platforms = platforms or list(PLATFORMS.keys())

    for platform in platforms:
        result = await scrape_platform(client, platform, title, slug)
        if result:
            results[platform] = result
        await asyncio.sleep(REQUEST_DELAY)

    return {
        "occupation": occupation,
        "results": results
    }


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scrape job postings")
    parser.add_argument("slug", nargs="?", help="Single occupation slug to scrape")
    parser.add_argument("--all", action="store_true", help="Scrape all occupations")
    parser.add_argument("--platform", choices=list(PLATFORMS.keys()), help="Specific platform")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of occupations")
    args = parser.parse_args()

    occupations = load_occupations()

    if args.slug:
        # Single occupation
        occ = next((o for o in occupations if o["slug"] == args.slug), None)
        if not occ:
            print(f"Occupation not found: {args.slug}")
            return
        occupations = [occ]
    elif not args.all:
        print("Use --all to scrape all occupations, or specify a slug")
        return

    if args.limit:
        occupations = occupations[:args.limit]

    platforms = [args.platform] if args.platform else list(PLATFORMS.keys())

    print(f"Will scrape {len(occupations)} occupations from {platforms}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for occ in occupations:
            await scrape_occupation(client, occ, platforms)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
