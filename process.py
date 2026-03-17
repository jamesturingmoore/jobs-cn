"""
Process scraped data and generate Markdown pages for each occupation.

Creates pages/{slug}.md files with job descriptions suitable for LLM analysis.

Usage:
    uv run python process.py [slug]
    uv run python process.py --all
"""

import json
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "beautifulsoup4"], check=True)
    from bs4 import BeautifulSoup


HTML_DIR = Path("html")
PAGES_DIR = Path("pages")
DATA_DIR = Path("data")


def generate_markdown(slug: str, occupation: dict) -> str:
    """Generate Markdown description for an occupation."""
    title = occupation["title"]
    category = occupation["category"]

    # Load parsed data
    data_file = DATA_DIR / f"{slug}.json"
    parsed_data = {}
    if data_file.exists():
        with open(data_file, encoding="utf-8") as f:
            parsed_data = json.load(f)

    # Build markdown
    md = f"""# {title}

## 基本信息

- **职业代码**: {occupation['code']}
- **职业类别**: {category}
- **数据来源**: 中国招聘平台聚合数据

"""

    # Add salary info
    salary = parsed_data.get("salary", {})
    if salary.get("median"):
        md += f"""## 薪资水平

- **月薪范围**: ¥{salary['min']:,.0f} - ¥{salary['max']:,.0f}
- **中位数**: ¥{salary['median']:,.0f}

"""

    # Add education/experience
    edu = parsed_data.get("education_mode")
    exp = parsed_data.get("experience_mode")
    if edu or exp:
        md += "## 任职要求\n\n"
        if edu:
            md += f"- **学历要求**: {edu}\n"
        if exp:
            md += f"- **经验要求**: {exp}\n"
        md += "\n"

    # Add job listings summary
    jobs = parsed_data.get("jobs", [])
    if jobs:
        md += "## 典型职位示例\n\n"
        for i, job in enumerate(jobs[:5]):
            salary_str = ""
            if job.get("salary"):
                s = job["salary"]
                salary_str = f" (¥{s['min']:,.0f}-¥{s['max']:,.0f})"
            md += f"{i+1}. **{job.get('title', '未知职位')}** - {job.get('company', '未知公司')}{salary_str}\n"
        md += "\n"

    # Add statistics
    job_count = parsed_data.get("job_count", 0)
    if job_count:
        md += f"""## 市场统计

- **在招职位数**: {job_count}
- **数据更新时间**: {parsed_data.get('scraped_at', '未知')}

"""

    return md


def process_occupation(slug: str) -> bool:
    """Process a single occupation and generate Markdown."""
    # Load occupation data
    with open("occupations.json", encoding="utf-8") as f:
        occupations = json.load(f)

    occ = next((o for o in occupations if o["slug"] == slug), None)
    if not occ:
        print(f"Occupation not found: {slug}")
        return False

    # Generate markdown
    md = generate_markdown(slug, occ)

    # Save
    output_file = PAGES_DIR / f"{slug}.md"
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Generated: {output_file}")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("slug", nargs="?", help="Occupation slug")
    parser.add_argument("--all", action="store_true", help="Process all")
    args = parser.parse_args()

    if args.slug:
        process_occupation(args.slug)
    elif args.all:
        with open("occupations.json", encoding="utf-8") as f:
            occupations = json.load(f)

        for occ in occupations:
            process_occupation(occ["slug"])
    else:
        print("Specify slug or --all")


if __name__ == "__main__":
    main()
