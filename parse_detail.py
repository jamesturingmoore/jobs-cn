"""
Parse scraped job posting HTML to extract structured data.

Extracts:
- Salary range (min, max, median)
- Education requirements
- Experience requirements
- Job description summary

Usage:
    uv run python parse_detail.py [slug]
    uv run python parse_detail.py --all
"""

import json
import re
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "beautifulsoup4"], check=True)
    from bs4 import BeautifulSoup


HTML_DIR = Path("html")
DATA_DIR = Path("data")


def parse_salary(text: str) -> dict | None:
    """
    Parse Chinese salary text to extract range.

    Formats:
    - "10-15K" -> {"min": 10000, "max": 15000, "median": 12500}
    - "10K-15K" -> same
    - "1-1.5万" -> same
    - "面议" -> None
    """
    text = text.replace(" ", "").replace("k", "K").replace("万", "W")

    # Pattern: 10-15K or 10K-15K
    match = re.search(r'(\d+(?:\.\d+)?)[K·-]?(\d+(?:\.\d+)?)K', text)
    if match:
        min_sal = float(match.group(1)) * 1000
        max_sal = float(match.group(2)) * 1000
        return {"min": min_sal, "max": max_sal, "median": (min_sal + max_sal) / 2}

    # Pattern: 1-1.5W (万)
    match = re.search(r'(\d+(?:\.\d+)?)[W·-]?(\d+(?:\.\d+)?)W', text)
    if match:
        min_sal = float(match.group(1)) * 10000
        max_sal = float(match.group(2)) * 10000
        return {"min": min_sal, "max": max_sal, "median": (min_sal + max_sal) / 2}

    # Single value: 10K
    match = re.search(r'(\d+(?:\.\d+)?)K', text)
    if match:
        sal = float(match.group(1)) * 1000
        return {"min": sal, "max": sal, "median": sal}

    return None


def parse_education(text: str) -> str | None:
    """Extract education level from text."""
    text = text.lower()

    edu_map = {
        "博士": "博士",
        "博士研究生": "博士",
        "硕士": "硕士",
        "硕士研究生": "硕士",
        "本科": "本科",
        "大学本科": "本科",
        "大专": "大专",
        "专科": "大专",
        "高中": "高中/中专",
        "中专": "高中/中专",
        "技校": "高中/中专",
        "初中": "初中及以下",
        "不限": "不限",
        "学历不限": "不限",
    }

    for keyword, level in edu_map.items():
        if keyword in text:
            return level

    return None


def parse_experience(text: str) -> str | None:
    """Extract experience requirement from text."""
    # Pattern: X年经验, X-Y年经验
    match = re.search(r'(\d+)-(\d+)年', text)
    if match:
        return f"{match.group(1)}-{match.group(2)}年"

    match = re.search(r'(\d+)年.*经验', text)
    if match:
        years = int(match.group(1))
        if years == 0:
            return "不限"
        elif years <= 1:
            return "1年以下"
        elif years <= 3:
            return "1-3年"
        elif years <= 5:
            return "3-5年"
        else:
            return "5年以上"

    if "不限" in text or "无需经验" in text:
        return "不限"

    return None


def parse_boss_html(html: str) -> list[dict]:
    """Parse BOSS直聘 search results."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Job cards
    cards = soup.select(".job-list-box .job-card-wrapper")
    for card in cards[:20]:  # Limit to 20 results
        try:
            title_el = card.select_one(".job-name")
            title = title_el.get_text(strip=True) if title_el else ""

            salary_el = card.select_one(".salary")
            salary_text = salary_el.get_text(strip=True) if salary_el else ""
            salary = parse_salary(salary_text)

            # Tags usually contain education, experience
            tags_el = card.select(".tag-list li")
            tags = [t.get_text(strip=True) for t in tags_el]

            education = None
            experience = None
            for tag in tags:
                if not education:
                    education = parse_education(tag)
                if not experience:
                    experience = parse_experience(tag)

            company_el = card.select_one(".company-name a")
            company = company_el.get_text(strip=True) if company_el else ""

            jobs.append({
                "title": title,
                "company": company,
                "salary": salary,
                "education": education,
                "experience": experience,
            })
        except Exception as e:
            continue

    return jobs


def parse_zhilian_html(html: str) -> list[dict]:
    """Parse 智联招聘 search results."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Job items
    items = soup.select(".positionlist .positionlist__item")
    for item in items[:20]:
        try:
            title_el = item.select_one(".positionlist__item-position a")
            title = title_el.get_text(strip=True) if title_el else ""

            salary_el = item.select_one(".positionlist__item-salary")
            salary_text = salary_el.get_text(strip=True) if salary_el else ""
            salary = parse_salary(salary_text)

            # Info tags
            info_el = item.select_one(".positionlist__item-position-info")
            info_text = info_el.get_text(strip=True) if info_el else ""

            education = parse_education(info_text)
            experience = parse_experience(info_text)

            company_el = item.select_one(".positionlist__item-company a")
            company = company_el.get_text(strip=True) if company_el else ""

            jobs.append({
                "title": title,
                "company": company,
                "salary": salary,
                "education": education,
                "experience": experience,
            })
        except Exception:
            continue

    return jobs


def aggregate_job_data(slug: str) -> dict:
    """Aggregate job data from all platforms for an occupation."""
    all_jobs = []

    # Parse BOSS直聘
    boss_file = HTML_DIR / "boss" / f"{slug}.json"
    if boss_file.exists():
        with open(boss_file, encoding="utf-8") as f:
            data = json.load(f)
            jobs = parse_boss_html(data.get("html", ""))
            all_jobs.extend(jobs)

    # Parse 智联招聘
    zhilian_file = HTML_DIR / "zhilian" / f"{slug}.json"
    if zhilian_file.exists():
        with open(zhilian_file, encoding="utf-8") as f:
            data = json.load(f)
            jobs = parse_zhilian_html(data.get("html", ""))
            all_jobs.extend(jobs)

    if not all_jobs:
        return None

    # Aggregate statistics
    salaries = [j["salary"]["median"] for j in all_jobs if j.get("salary")]
    educations = [j["education"] for j in all_jobs if j.get("education")]
    experiences = [j["experience"] for j in all_jobs if j.get("experience")]

    from statistics import median, mode
    from collections import Counter

    result = {
        "slug": slug,
        "job_count": len(all_jobs),
        "salary": {
            "min": min(salaries) if salaries else None,
            "max": max(salaries) if salaries else None,
            "median": median(salaries) if salaries else None,
        },
        "education_mode": Counter(educations).most_common(1)[0][0] if educations else None,
        "experience_mode": Counter(experiences).most_common(1)[0][0] if experiences else None,
        "jobs": all_jobs[:50],  # Keep sample
    }

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("slug", nargs="?", help="Occupation slug")
    parser.add_argument("--all", action="store_true", help="Parse all")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.slug:
        result = aggregate_job_data(args.slug)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.all:
        with open("occupations.json", encoding="utf-8") as f:
            occupations = json.load(f)

        for occ in occupations:
            slug = occ["slug"]
            result = aggregate_job_data(slug)
            if result:
                output_file = DATA_DIR / f"{slug}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"Parsed: {slug} ({result['job_count']} jobs)")
    else:
        print("Specify slug or --all")


if __name__ == "__main__":
    main()
