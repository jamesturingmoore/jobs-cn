"""
Score occupations for AI exposure using OpenAI-compatible API.

Default behavior: Load pre-cached scores from scores.json.

Optional re-scoring:
    uv run python score.py --refresh              # Re-score all
    uv run python score.py --refresh --start 0 --end 100  # Partial

Environment variables (.env):
    OPENAI_API_BASE - API endpoint (default: OpenAI)
    OPENAI_API_KEY - Your API key
    OPENAI_MODEL - Model to use (default: gpt-4o)

Output: scores.json
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "python-dotenv"], check=True)
    from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError:
    import subprocess
    subprocess.run(["uv", "pip", "install", "openai"], check=True)
    from openai import OpenAI

load_dotenv()

# Configuration
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Chinese scoring prompt
SCORING_PROMPT = """你是一位专业的劳动力市场分析师。阅读以下来自中国招聘平台的职业描述。

请评估该职业的整体 **AI暴露度**，评分范围 0-10。

AI暴露度衡量：AI将如何重塑这个职业？请同时考虑：
- 直接影响：AI自动化目前由人类完成的任务
- 间接影响：AI使每位工作者效率提升，导致需求减少

关键信号：该职业的工作产品是否从根本上属于数字化。
如果工作可以在家庭办公室完全通过计算机完成，AI暴露度天生就很高（7+）。

评分锚点：
- 0-1：最低暴露（建筑工人、园林工人）
- 2-3：低暴露（电工、水管工、消防员）
- 4-5：中等暴露（注册护士、警察、兽医）
- 6-7：高暴露（教师、经理、会计师、记者）
- 8-9：极高暴露（软件开发、平面设计、翻译、数据分析师）
- 10：最大暴露（数据录入员、电话推销员）

请仅以JSON格式回复：
{"exposure": <0-10>, "rationale": "<2-3句解释关键因素>"}
"""


def load_occupation_description(slug: str) -> str | None:
    """Load markdown description for an occupation."""
    md_file = Path("pages") / f"{slug}.md"
    if md_file.exists():
        with open(md_file, encoding="utf-8") as f:
            return f.read()
    return None


def score_occupation(client: OpenAI, slug: str, title: str, description: str) -> dict:
    """Score a single occupation using the API."""
    messages = [
        {"role": "system", "content": SCORING_PROMPT},
        {"role": "user", "content": f"## {title}\n\n{description}"}
    ]

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=200,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON response
        # Handle markdown code blocks
        if "```" in content:
            import re
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if match:
                content = match.group(1)

        result = json.loads(content)
        return {
            "slug": slug,
            "exposure": int(result.get("exposure", 5)),
            "rationale": result.get("rationale", "")[:200]
        }

    except Exception as e:
        print(f"  ERROR: {e}")
        return {
            "slug": slug,
            "exposure": 5,
            "rationale": f"评分失败: {str(e)[:100]}"
        }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Re-score using API")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--end", type=int, default=-1, help="End index (-1 for all)")
    args = parser.parse_args()

    # Load occupations
    with open("occupations.json", encoding="utf-8") as f:
        occupations = json.load(f)

    # Load existing scores
    scores_file = Path("scores.json")
    existing_scores = {}
    if scores_file.exists():
        with open(scores_file, encoding="utf-8") as f:
            for s in json.load(f):
                existing_scores[s["slug"]] = s

    if not args.refresh:
        # Just report existing scores
        print(f"Loaded {len(existing_scores)} pre-cached scores")
        print("Use --refresh to re-score using API")
        return

    # Check API configuration
    if not API_KEY:
        print("ERROR: OPENAI_API_KEY not set")
        print("Please set it in .env file")
        sys.exit(1)

    client = OpenAI(base_url=API_BASE, api_key=API_KEY)

    # Determine range
    start = args.start
    end = args.end if args.end > 0 else len(occupations)
    to_score = occupations[start:end]

    print(f"Scoring {len(to_score)} occupations ({start} to {end})...")

    new_scores = []
    for i, occ in enumerate(to_score):
        slug = occ["slug"]
        title = occ["title"]

        # Check if already scored
        if slug in existing_scores and not args.refresh:
            new_scores.append(existing_scores[slug])
            continue

        print(f"[{start + i + 1}/{end}] {title}...")

        # Get description
        desc = load_occupation_description(slug)
        if not desc:
            desc = f"职业名称: {title}\n类别: {occ['category']}"

        # Score
        result = score_occupation(client, slug, title, desc)
        new_scores.append(result)

        # Rate limiting
        time.sleep(0.5)

    # Merge with existing and save
    all_scores = list(existing_scores.values())
    for s in new_scores:
        # Update or add
        for i, existing in enumerate(all_scores):
            if existing["slug"] == s["slug"]:
                all_scores[i] = s
                break
        else:
            all_scores.append(s)

    with open(scores_file, "w", encoding="utf-8") as f:
        json.dump(all_scores, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(all_scores)} scores to {scores_file}")


if __name__ == "__main__":
    main()
