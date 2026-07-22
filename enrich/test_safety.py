#!/usr/bin/env python3
"""safety.classify_side_effects 회귀 테스트. 프레임워크 없이 순수 실행.

  python enrich/test_safety.py   → 모두 통과면 "OK N cases", 실패 시 비0 종료
"""
import sys

from safety import classify_side_effects

CASES = [
    # (텍스트, 기대값)
    ("Git: Discard All Changes git.clean", "irreversible"),
    ("변경사항 전부 되돌려", "irreversible"),
    ("Delete Folder", "irreversible"),
    ("Publish to Marketplace", "irreversible"),
    ("Git: Push", "irreversible"),
    ("확장 제거", "irreversible"),
    ("ESLint: Fix all auto-fixable Problems eslint.executeAutofix", "reversible"),
    ("파일 포맷팅 format document", "reversible"),
    ("Rename Symbol", "reversible"),
    ("Git: Commit", "reversible"),
    ("새 파일 생성", "reversible"),
    ("Git: View History git.viewHistory", "read_only"),
    ("Go to Symbol in File", "read_only"),
    ("open a new terminal", "read_only"),
    ("심볼로 이동", "read_only"),
]


def main() -> int:
    fails = []
    for text, expected in CASES:
        got = classify_side_effects(text)
        if got != expected:
            fails.append(f"  FAIL {text!r}: 기대 {expected}, 실제 {got}")
    if fails:
        print("FAIL:\n" + "\n".join(fails))
        return 1
    print(f"OK {len(CASES)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
