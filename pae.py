#!/usr/bin/env python3
"""PAESTRO 오프라인 툴체인 통합 CLI.

  python pae.py crawl              오픈소스 크롤 → 레지스트리
  python pae.py stats [--risky]    레지스트리 통계/관측
  python pae.py search "질의"      번호 후보 검색
  python pae.py index [--post URL] 엔진 색인 레코드 생성/투입
  python pae.py validate           매니페스트 계약 검증
  python pae.py demo               이질 소스 통합 파이프라인
  python pae.py check              CI 3종 로컬 실행(safety·validate·demo)
"""
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS = {
    "crawl": "registry/crawl.py",
    "search": "registry/search.py",
    "stats": "registry/stats.py",
    "index": "registry/to_index.py",
    "validate": "schemas/validate.py",
    "enrich": "enrich/enrich.py",
    "eval": "eval/run_eval.py",
    "demo": "demo/pipeline.py",
}
CHECK = ["enrich/test_safety.py", "schemas/validate.py", "demo/pipeline.py", "eval/regression.py"]


def run(script: str, args: list[str]) -> int:
    return subprocess.call([sys.executable, script, *args])


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = sys.argv[1], sys.argv[2:]

    if cmd == "check":
        failed = [s for s in CHECK if run(s, []) != 0]
        print(("\n✗ 실패: " + ", ".join(failed)) if failed else f"\n✓ CI {len(CHECK)}종 통과")
        return 1 if failed else 0
    if cmd not in SCRIPTS:
        print(f"알 수 없는 명령: {cmd}\n")
        print(__doc__)
        return 2
    return run(SCRIPTS[cmd], rest)


if __name__ == "__main__":
    raise SystemExit(main())
