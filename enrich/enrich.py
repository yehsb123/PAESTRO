#!/usr/bin/env python3
"""PAESTRO #2 어댑터 LLM 보강 배치 (enrich).

parse 단계(tools/scan.js)가 만든 뼈대 카탈로그를 읽어 capability마다
  when_to_use · when_not_to_use · keywords · side_effects · args_schema
를 채운다. side_effects 재분류로 확장의 승인 게이트(irreversible)가 비로소 실재화된다.

두 모드
  --heuristic   API 없이 규칙 기반(빠른 기본값 + 안전 게이트 실재화)
  (기본)         ANTHROPIC_API_KEY 있으면 Claude로 고품질 보강, 없으면 heuristic 자동 폴백

입력  catalog.json  — scan.js 출력(중첩 {plugin,capabilities[]} 배열) 또는 flat capability 배열 모두 허용
출력  out/enriched_catalog.json  — 보강된 flat capability 배열 (schemas/capability-manifest 계약 준수)

실행
  python enrich/enrich.py --in enrich/sample_catalog.json --out enrich/out --heuristic
  ANTHROPIC_API_KEY=... python enrich/enrich.py --in catalog.json --out enrich/out
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

MODEL = os.environ.get("PAESTRO_ENRICH_MODEL", "claude-sonnet-5")  # 최고 품질은 claude-opus-4-8
BATCH = int(os.environ.get("PAESTRO_ENRICH_BATCH", "15"))

# ── side_effects 규칙 (보수적: 애매하면 더 위험한 쪽으로) ──────────────────
_IRREVERSIBLE = re.compile(
    r"\b(delete|remove|reset|revert|discard|drop|destroy|wipe|clean|prune|purge|"
    r"uninstall|publish|deploy|release|push|force|overwrite|erase|clear\s*all)\b|"
    r"삭제|제거|초기화|되돌리|배포|발행|덮어",
    re.I,
)
_REVERSIBLE = re.compile(
    r"\b(fix|format|rename|edit|apply|add|create|generate|write|save|refactor|"
    r"organize|sort|insert|replace|install|update|move|convert|import|commit|stage)\b|"
    r"수정|고치|정리|생성|저장|추가|변경|바꾸|이동|커밋",
    re.I,
)


def classify_side_effects(text: str) -> str:
    if _IRREVERSIBLE.search(text):
        return "irreversible"
    if _REVERSIBLE.search(text):
        return "reversible"
    return "read_only"


# ── 카탈로그 로딩 & flatten ──────────────────────────────────────────────
def load_flat(path: Path) -> list[dict]:
    """중첩(manifest) 또는 flat 카탈로그 → flat capability 리스트."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    flat: list[dict] = []
    for entry in data:
        if isinstance(entry, dict) and "capabilities" in entry:  # 중첩 manifest
            plugin = entry.get("plugin", {})
            pid = plugin.get("id", "unknown")
            runtime = plugin.get("runtime", "vscode")
            for c in entry["capabilities"]:
                c = dict(c)
                c.setdefault("plugin", pid)
                c.setdefault("runtime", runtime)
                flat.append(c)
        else:  # 이미 flat
            flat.append(dict(entry))
    return flat


def command_of(cap: dict) -> str:
    inv = cap.get("invocation", {}) or {}
    return inv.get("command") or inv.get("tool") or inv.get("path") or ""


def context_text(cap: dict) -> str:
    return " ".join(
        str(x) for x in [cap.get("intent", ""), " ".join(cap.get("keywords", []) or []), command_of(cap)] if x
    )


def build_embedding_text(cap: dict) -> str:
    parts = [cap.get("intent", ""), " ".join(cap.get("keywords", []) or []), cap.get("when_to_use", ""), command_of(cap)]
    return " ".join(p for p in parts if p).strip()


# ── heuristic 보강 ────────────────────────────────────────────────────────
def enrich_heuristic(cap: dict) -> dict:
    ctx = context_text(cap)
    if not (cap.get("side_effects") and cap["side_effects"] != "read_only"):
        cap["side_effects"] = classify_side_effects(ctx)
    if not cap.get("keywords"):
        toks = re.split(r"[\s._:\-/]+", ctx.lower())
        cap["keywords"] = sorted({t for t in toks if len(t) > 1})[:8]
    cap.setdefault("when_to_use", "")
    cap.setdefault("when_not_to_use", "")
    inv = cap.setdefault("invocation", {})
    inv.setdefault("args_schema", None)
    cap["embedding_text"] = build_embedding_text(cap)
    return cap


# ── LLM 보강 (Anthropic) ─────────────────────────────────────────────────
_PROMPT = """너는 의미 기반 도구 라우터(PAESTRO)를 위해 VS Code 명령 capability를 보강한다.
아래 각 capability에 대해 JSON 객체를 채워라. 반드시 JSON 배열만 출력(설명 금지).

각 원소:
{{"id": <그대로>, "intent": <한국어 한 줄 의도>, "keywords": [한/영 동의어 5~8개],
 "when_to_use": <이 도구를 골라야 하는 상황(한국어)>, "when_not_to_use": <혼동되는 다른 도구로 안내>,
 "side_effects": "read_only"|"reversible"|"irreversible", "args_schema": <JSON Schema object 또는 null>}}

side_effects 판단(보수적): 삭제/초기화/배포/발행/force = irreversible, 파일·상태 변경 가능=reversible, 조회/이동/표시=read_only.

capabilities:
{items}"""


def enrich_llm(caps: list[dict]) -> list[dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("  anthropic 미설치 → heuristic 폴백 (pip install -r enrich/requirements.txt)", file=sys.stderr)
        return [enrich_heuristic(c) for c in caps]

    client = Anthropic()
    out: list[dict] = []
    for i in range(0, len(caps), BATCH):
        chunk = caps[i : i + BATCH]
        items = json.dumps(
            [{"id": c["id"], "title": c.get("intent", ""), "command": command_of(c), "plugin": c.get("plugin", "")} for c in chunk],
            ensure_ascii=False,
        )
        msg = client.messages.create(
            model=MODEL, max_tokens=4096,
            messages=[{"role": "user", "content": _PROMPT.format(items=items)}],
        )
        text = msg.content[0].text.strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
        by_id = {e["id"]: e for e in json.loads(text)}
        for c in chunk:
            e = by_id.get(c["id"], {})
            for k in ("intent", "keywords", "when_to_use", "when_not_to_use", "side_effects"):
                if e.get(k):
                    c[k] = e[k]
            c.setdefault("invocation", {})["args_schema"] = e.get("args_schema")
            c["embedding_text"] = build_embedding_text(c)
            out.append(c)
        print(f"  보강 {min(i + BATCH, len(caps))}/{len(caps)}", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", default="enrich/out")
    ap.add_argument("--heuristic", action="store_true", help="API 없이 규칙 기반만")
    args = ap.parse_args()

    caps = load_flat(Path(args.inp))
    use_llm = not args.heuristic and bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"입력 {len(caps)}개 capability · 모드={'LLM(' + MODEL + ')' if use_llm else 'heuristic'}", file=sys.stderr)

    enriched = enrich_llm(caps) if use_llm else [enrich_heuristic(c) for c in caps]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "enriched_catalog.json"
    out_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    counts: dict[str, int] = {}
    for c in enriched:
        counts[c["side_effects"]] = counts.get(c["side_effects"], 0) + 1
    print(f"→ {out_path} 저장 · side_effects {counts}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
