#!/usr/bin/env python3
"""레지스트리 통계/관측 [6. 거버넌스] — catalog 분석 리포트 (엔진 불필요, 의존성 0).

런타임·안전등급·플러그인별 분포와 승인 대상(irreversible) 목록을 낸다. 거버넌스/감사 기초.

실행
  python registry/stats.py                 # 요약
  python registry/stats.py --risky         # irreversible 전량 나열
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent


def load() -> list[dict]:
    for name in ("registry/catalog.json", "registry/catalog.sample.json"):
        p = ROOT / name
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            caps = []
            for m in data:
                for c in m["capabilities"]:
                    c = dict(c)
                    c["_plugin"] = m["plugin"]["id"]
                    c["_runtime"] = m["plugin"]["runtime"]
                    caps.append(c)
            return caps
    raise SystemExit("catalog 없음 — 먼저 python registry/crawl.py")


def bar(n: int, total: int, width: int = 24) -> str:
    fill = round(width * n / total) if total else 0
    return "█" * fill + "·" * (width - fill)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--risky", action="store_true", help="irreversible 전량 나열")
    args = ap.parse_args()

    caps = load()
    total = len(caps)
    by_rt = Counter(c["_runtime"] for c in caps)
    by_se = Counter(c["side_effects"] for c in caps)
    by_pl = Counter(c["_plugin"] for c in caps)

    print(f"\n═══ PAESTRO 레지스트리 · capability {total}개 ═══\n")
    print("런타임")
    for k, n in by_rt.most_common():
        print(f"  {k:10} {n:5}  {bar(n, total)}")
    print("\n안전 등급")
    for k in ("read_only", "reversible", "irreversible"):
        n = by_se.get(k, 0)
        tag = " ⚠ 승인 게이트" if k == "irreversible" else ""
        print(f"  {k:12} {n:5}  {bar(n, total)}{tag}")
    print("\n상위 플러그인")
    for k, n in by_pl.most_common(8):
        print(f"  {k:22} {n:5}")

    if args.risky:
        print(f"\n═══ 승인 필요(irreversible) {by_se.get('irreversible',0)}개 ═══")
        for c in sorted((c for c in caps if c["side_effects"] == "irreversible"), key=lambda c: c["_plugin"]):
            print(f"  [{c['_plugin']}] {c.get('intent','')[:50]}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
