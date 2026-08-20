#!/usr/bin/env python3
"""PAESTRO 오프라인 툴체인 통합 CLI.

  python pae.py crawl              오픈소스 크롤 → 레지스트리
  python pae.py stats [--risky]    레지스트리 통계/관측
  python pae.py search "질의"      번호 후보 검색
  python pae.py orchestrate "복합요청"  멀티스텝 → 크로스-런타임 계획
  python pae.py index [--post URL] 엔진 색인 레코드 생성/투입
  python pae.py validate           매니페스트 계약 검증
  python pae.py demo               이질 소스 통합 파이프라인
  python pae.py check              CI(safety·validate·demo·regression) 로컬 실행
  python pae.py doctor             환경 진단(의존성·카탈로그·엔진)
"""
import json
import subprocess
import sys
import urllib.request
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS = {
    "crawl": "registry/crawl.py",
    "search": "registry/search.py",
    "orchestrate": "registry/orchestrate.py",
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


def doctor() -> int:
    """환경 진단 — 의존성·카탈로그·엔진 상태를 점검한다."""
    ok = "✓"
    warn = "•"
    print("\n═══ PAESTRO 환경 진단 ═══\n")
    print(f"  {ok} Python {sys.version.split()[0]}")

    print("\n의존성 (오프라인 툴체인은 stdlib만 필요)")
    for mod, why in [("fastembed", "엔진 임베딩"), ("chromadb", "엔진 색인"),
                     ("fastapi", "엔진 서버"), ("anthropic", "LLM 보강·planner(선택)")]:
        have = find_spec(mod) is not None
        print(f"  {ok if have else warn} {mod:10} {'설치됨' if have else '미설치'} — {why}")

    print("\n레지스트리")
    cat = ROOT / "registry" / "catalog.json"
    if cat.exists():
        n = sum(len(m["capabilities"]) for m in json.loads(cat.read_text(encoding="utf-8")))
        print(f"  {ok} catalog.json — {n} capability ({cat.stat().st_size // 1024} KB)")
    else:
        print(f"  {warn} catalog.json 없음 — `python pae.py crawl`로 생성")

    print("\n엔진 (127.0.0.1:8756)")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8756/health", timeout=3) as r:
            h = json.loads(r.read())
        print(f"  {ok} 실행 중 — 모델 {h.get('model', '?').split('/')[-1]} · 색인 {h.get('count', 0)}")
    except Exception:
        print(f"  {warn} 미실행 — engine/에서 `uvicorn app:app --port 8756` (오프라인 기능엔 불필요)")

    key = bool(__import__("os").environ.get("ANTHROPIC_API_KEY"))
    print(f"\nLLM 보강/planner: ANTHROPIC_API_KEY {'설정됨 ✓' if key else '미설정 • (설정 시 KO 정확도↑·LLM planner 활성)'}")
    print()
    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = sys.argv[1], sys.argv[2:]

    if cmd == "check":
        failed = [s for s in CHECK if run(s, []) != 0]
        print(("\n✗ 실패: " + ", ".join(failed)) if failed else f"\n✓ CI {len(CHECK)}종 통과")
        return 1 if failed else 0

    if cmd == "doctor":
        return doctor()
    if cmd not in SCRIPTS:
        print(f"알 수 없는 명령: {cmd}\n")
        print(__doc__)
        return 2
    return run(SCRIPTS[cmd], rest)


if __name__ == "__main__":
    raise SystemExit(main())
