"""检查指定范围的新提交标题；不检查或改写既有历史。"""

import argparse
import re
import subprocess
import sys

PATTERN = re.compile(
    r"^（(?:A覃锐谦|B祝祎帆)）"
    r"(feat|fix|refactor|test|docs|style|perf|build|ci|chore|revert)"
    r"(?:\([^\r\n()]+\))?[：:]\s*([^\r\n]+)$"
)


def valid_subject(subject):
    match = PATTERN.fullmatch(subject)
    if not match:
        return False
    description = match.group(2).strip()
    return bool(re.search(r"[\u3400-\u9fff]", description)) and len(description) >= 6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    for ref in (args.base, args.head):
        if ref.startswith("-"):
            parser.error("引用不能以连字符开头")
        subprocess.run(["git", "rev-parse", "--verify", ref + "^{commit}"],
                       check=True, capture_output=True)
    result = subprocess.run(
        ["git", "log", "--format=%H%x09%s", f"{args.base}..{args.head}", "--"],
        check=True, capture_output=True, text=True, encoding="utf-8"
    )
    records = [line.split("\t", 1) for line in result.stdout.splitlines()]
    errors = [(sha, title) for sha, title in records if not valid_subject(title)]
    for sha, title in errors:
        print(f"不合规范 {sha[:10]}: {title}")
    print(f"新提交 {len(records)}，标题错误 {len(errors)}。正文与含义仍需人工审查。")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
