"""
Generate structured CSV from occupation data and scraped job listings.

Creates occupations.csv with columns:
- title, code, category, sub_category, slug
- median_pay_monthly, median_pay_annual
- entry_education, work_experience
- industry, num_jobs_estimate
- outlook_growth_pct, outlook_desc
- salary_source, url

Usage:
    uv run python make_csv.py
"""

import csv
import json
from pathlib import Path

DATA_DIR = Path("data")


def load_occupations() -> list[dict]:
    with open("occupations.json", encoding="utf-8") as f:
        return json.load(f)


def load_job_data(slug: str) -> dict | None:
    data_file = DATA_DIR / f"{slug}.json"
    if data_file.exists():
        with open(data_file, encoding="utf-8") as f:
            return json.load(f)
    return None


def estimate_job_count(parsed_data: dict | None) -> int | None:
    """
    Estimate total employment from job posting count.

    Uses a simple multiplier based on platform penetration rate.
    """
    if not parsed_data:
        return None

    job_postings = parsed_data.get("job_count", 0)
    if job_postings == 0:
        return None

    # Assume platforms represent ~30% of total job market
    # and each posting represents ~5 actual positions
    multiplier = 5 / 0.3
    return int(job_postings * multiplier)


def main():
    occupations = load_occupations()
    rows = []

    for occ in occupations:
        slug = occ["slug"]
        parsed = load_job_data(slug)

        salary = parsed.get("salary", {}) if parsed else {}
        median_monthly = salary.get("median")
        median_annual = median_monthly * 12 if median_monthly else None

        row = {
            "title": occ["title"],
            "code": occ["code"],
            "category": occ["category"],
            "sub_category": occ.get("sub_category", ""),
            "slug": slug,
            "median_pay_monthly": int(median_monthly) if median_monthly else "",
            "median_pay_annual": int(median_annual) if median_annual else "",
            "entry_education": parsed.get("education_mode", "") if parsed else "",
            "work_experience": parsed.get("experience_mode", "") if parsed else "",
            "industry": "",
            "num_jobs_estimate": estimate_job_count(parsed),
            "outlook_growth_pct": "",
            "outlook_desc": "",
            "salary_source": "招聘平台数据" if parsed else "",
            "url": "",
        }
        rows.append(row)

    # Write CSV
    fieldnames = [
        "title", "code", "category", "sub_category", "slug",
        "median_pay_monthly", "median_pay_annual",
        "entry_education", "work_experience",
        "industry", "num_jobs_estimate",
        "outlook_growth_pct", "outlook_desc",
        "salary_source", "url"
    ]

    with open("occupations.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated occupations.csv with {len(rows)} rows")

    # Stats
    with_salary = sum(1 for r in rows if r["median_pay_monthly"])
    with_education = sum(1 for r in rows if r["entry_education"])
    print(f"  - {with_salary} have salary data")
    print(f"  - {with_education} have education data")


if __name__ == "__main__":
    main()
