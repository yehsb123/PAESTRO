#!/usr/bin/env python3
"""레지스트리 오프라인 검색 — "자연어 → 번호 후보 목록" (엔진 불필요, 의존성 0).

크롤한 catalog.json(없으면 catalog.sample.json) 위에서 렉시컬 랭킹으로 후보를 뽑아
PAESTRO의 번호 선택 UX 그대로 보여준다. `5`는 항상 '직접 지정/설정' 고정.
위험(irreversible) 후보는 ⚠로 표시(실행 시 승인 게이트 대상).

주의: 오프라인 렉시컬이라 한국어 질의↔영어 명령은 약하다(그게 엔진 다국어 임베딩의 존재 이유).
실검색 품질은 엔진 /retrieve 로 측정한다(eval/).

실행
  python registry/search.py "git 커밋 그래프"
  python registry/search.py "format document" -k 4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # Windows 콘솔(cp949)에서도 UTF-8 출력 (한글·em-dash 안전)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent


def tokens(s: str) -> list[str]:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s or "")  # camelCase 분해
    return [t for t in re.split(r"[\s._:/!-]+", s.lower()) if len(t) > 1]


def load_catalog() -> list[dict]:
    for name in ("registry/catalog.json", "registry/catalog.sample.json"):
        p = ROOT / name
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            caps = []
            for m in data:
                for c in m["capabilities"]:
                    c = dict(c)
                    c["_plugin"] = m["plugin"]["id"]
                    caps.append(c)
            return caps
    raise SystemExit("catalog 없음 — 먼저 python registry/crawl.py 실행")


def search(query: str, caps: list[dict], k: int) -> list[dict]:
    q = tokens(query)
    qset = set(q)
    scored = []
    for c in caps:
        text = set(tokens(c.get("embedding_text") or c.get("intent", "")))
        kw = set(t.lower() for t in c.get("keywords", []))
        # 토큰 겹침(길이 가중) + 키워드 정확 일치 보너스
        score = sum(len(t) for t in q if t in text) + 3 * len(qset & kw)
        if score:
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:k]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("-k", type=int, default=4)
    args = ap.parse_args()
    query = " ".join(args.query)

    caps = load_catalog()
    hits = search(query, caps, args.k)

    print(f'\n"{query}" — 어떤 걸로 할까요?  (레지스트리 {len(caps)}개 중)\n')
    if not hits:
        print("  (매칭 없음 — 다른 표현으로 시도)")
    for i, c in enumerate(hits, 1):
        warn = " ⚠ 승인필요" if c.get("side_effects") == "irreversible" else ""
        print(f"  {i}. {c.get('intent','')[:52]:54} [{c['_plugin']}]{warn}")
    print(f"  5. 직접 지정 / 설정…\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
