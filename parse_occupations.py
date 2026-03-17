"""
Parse the Chinese occupation classification PDF (职业分类大典2022).

This parser extracts occupation codes and titles from the PDF.
Titles are cleaned by removing description text that follows.

Usage:
    uv run python parse_occupations.py

Output:
    occupations.json - List of all occupations with code, title, category, sub_category, slug
"""

import json
import re
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "pdfplumber"], check=True)
    import pdfplumber

try:
    from pypinyin import pinyin, Style
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "pypinyin"], check=True)
    from pypinyin import pinyin, Style


MAJOR_CATEGORIES = {
    "1": "党的机关、国家机关、群众团体和社会组织、企事业单位负责人",
    "2": "专业技术人员",
    "3": "办事人员和有关人员",
    "4": "社会生产服务和生活服务人员",
    "5": "农、林、牧、渔业生产及辅助人员",
    "6": "生产制造及有关人员",
    "7": "建筑和基础建造施工人员",
    "8": "军人",
    "9": "不便分类的其他从业人员"
}


def create_slug(title: str) -> str:
    py_list = pinyin(title, style=Style.NORMAL)
    slug = "-".join(py[0] for py in py_list if py[0].isalpha())
    return re.sub(r"-+", "-", slug).lower()


def clean_title(raw: str) -> str:
    """
    Extract clean occupation title from raw text.

    Strategy: Find the first sentence break that indicates description start.
    """
    # Common break patterns in Chinese
    # These typically indicate the start of description text
    break_patterns = [
        r'\s+',  # Space (Chinese rarely uses spaces between words)
        r'，',   # Comma
        r'。',   # Period
        r'、',   # Enumeration comma
        r'；',   # Semicolon
        r'：',   # Colon
        r'（',   # Open parenthesis
        r'是[，。]',  # "是" followed by punctuation
        r'指[，。]',  # "指" followed by punctuation
        r'包括[，。]',  # "包括" followed by punctuation
    ]

    # Find earliest break point
    min_idx = len(raw)
    for pattern in break_patterns:
        match = re.search(pattern, raw)
        if match and match.start() < min_idx and match.start() > 2:
            min_idx = match.start()

    title = raw[:min_idx].strip()

    # Remove trailing punctuation
    title = re.sub(r'[,;:;，。；：、]+$', '', title)

    # Remove trailing skill marker
    title = re.sub(r'\s*L$', '', title)

    # Validate
    if len(title) < 2:
        return ""

    # Must be mostly Chinese characters
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', title))
    if chinese_chars < len(title) * 0.6:
        return ""

    return title


def main():
    pdf_path = Path("reference/职业分类大典2022.pdf")
    if not pdf_path.exists():
        print("PDF not found")
        return

    occupations = {}
    code_pattern = re.compile(r'^(\d-\d{2}-\d{2}-\d{2})\s+(.+)$')

    with pdfplumber.open(str(pdf_path)) as pdf:
        print(f"Parsing {len(pdf.pages)} pages...")
        for page_num, page in enumerate(pdf.pages):
            if page_num % 100 == 0:
                print(f"  Page {page_num}...")
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                match = code_pattern.match(line.strip())
                if match:
                    code = match.group(1)
                    if code not in occupations:
                        title = clean_title(match.group(2))
                        if title:
                            occupations[code] = title

    # Convert to list
    result = []
    for code, title in sorted(occupations.items()):
        result.append({
            "code": code,
            "title": title,
            "category": MAJOR_CATEGORIES.get(code[0], ""),
            "sub_category": "",
            "slug": create_slug(title)
        })

    # Save
    with open("occupations.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nExtracted {len(result)} occupations")

    # Stats
    cat_counts = {}
    for occ in result:
        cat = occ["category"][:20] + "..." if len(occ["category"]) > 20 else occ["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    print("\nBy category:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
