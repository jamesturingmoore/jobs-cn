"""
Build compact JSON for the website by merging CSV stats with AI exposure scores.

Reads occupations.csv (for stats) and scores.json (for AI exposure).
Writes site/data.json.

Usage:
    uv run python build_site_data.py
"""

import csv
import json
import os
from pathlib import Path


def main():
    # Load AI exposure scores
    scores_file = Path("scores.json")
    scores = {}
    if scores_file.exists():
        with open(scores_file, encoding="utf-8") as f:
            scores_list = json.load(f)
            scores = {s["slug"]: s for s in scores_list}
        print(f"Loaded {len(scores)} AI exposure scores")
    else:
        print("Warning: scores.json not found, AI exposure will be null")

    # Load CSV stats
    csv_file = Path("occupations.csv")
    if not csv_file.exists():
        print("Error: occupations.csv not found")
        print("Run 'uv run python make_csv.py' first")
        return

    with open(csv_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} occupations from CSV")

    # Merge data
    data = []
    for row in rows:
        slug = row["slug"]
        score = scores.get(slug, {})

        # Parse monthly salary (prefer monthly over annual)
        pay_monthly = row.get("median_pay_monthly", "")
        pay = int(pay_monthly) if pay_monthly else None

        # Parse job count
        jobs = row.get("num_jobs_estimate", "")
        jobs = int(jobs) if jobs else None

        # Parse outlook
        outlook = row.get("outlook_growth_pct", "")
        outlook = int(outlook) if outlook else None

        data.append({
            "title": row["title"],
            "slug": slug,
            "category": row["category"],
            "pay": pay,  # Monthly salary in RMB
            "jobs": jobs,
            "outlook": outlook,
            "outlook_desc": row.get("outlook_desc", ""),
            "education": row.get("entry_education", ""),
            "exposure": score.get("exposure"),
            "exposure_rationale": score.get("rationale"),
            "url": row.get("url", ""),
        })

    # Ensure output directory
    output_dir = Path("site")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write data.json
    output_file = output_dir / "data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"Wrote {len(data)} occupations to {output_file}")

    # Summary stats
    total_jobs = sum(d["jobs"] for d in data if d["jobs"])
    with_pay = sum(1 for d in data if d["pay"])
    with_exposure = sum(1 for d in data if d["exposure"] is not None)

    print(f"\nSummary:")
    print(f"  Total jobs represented: {total_jobs:,}" if total_jobs else "  Total jobs: N/A")
    print(f"  With salary data: {with_pay}")
    print(f"  With AI exposure: {with_exposure}")


if __name__ == "__main__":
    main()
