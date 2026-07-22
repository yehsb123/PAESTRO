#!/usr/bin/env python3
"""examples/*.json 이 capability-manifest 계약을 지키는지 검증(의존성 0).

계약 드리프트(via/type 혼용, 중첩/flat 불일치, side_effects 오타 등) 재발 방지용.
CI/커밋 전 실행:  python schemas/validate.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")  # command는 camelCase(fixAll 등) → 대문자 허용
RUNTIMES = {"rest", "mcp", "cli", "graphql", "skill", "vscode"}
SIDE_EFFECTS = {"none", "read_only", "reversible", "irreversible"}
# runtime별 invocation 필수 필드 (type은 공통)
INVOCATION_REQUIRED = {
    "vscode": ["command"],
    "rest": ["method", "path"],
    "mcp": ["tool"],
    "cli": ["argv_template"],
}


def validate_manifest(m: dict) -> list[str]:
    errs: list[str] = []
    plugin = m.get("plugin")
    caps = m.get("capabilities")
    if not isinstance(plugin, dict):
        return ["plugin 객체 없음"]
    if not isinstance(caps, list) or not caps:
        return ["capabilities 배열 없음/비어있음"]

    pid = plugin.get("id", "")
    if not ID_RE.match(pid):
        errs.append(f"plugin.id 형식 위반: {pid!r}")
    if not plugin.get("version"):
        errs.append("plugin.version 없음")
    runtime = plugin.get("runtime")
    if runtime not in RUNTIMES:
        errs.append(f"plugin.runtime 잘못됨: {runtime!r}")

    for c in caps:
        cid = c.get("id", "")
        if not ID_RE.match(cid):
            errs.append(f"capability.id 형식 위반: {cid!r}")
        if not c.get("intent"):
            errs.append(f"[{cid}] intent 없음")
        if c.get("side_effects") not in SIDE_EFFECTS:
            errs.append(f"[{cid}] side_effects 잘못됨: {c.get('side_effects')!r}")
        inv = c.get("invocation")
        if not isinstance(inv, dict):
            errs.append(f"[{cid}] invocation 없음")
            continue
        itype = inv.get("type")
        if itype not in INVOCATION_REQUIRED:
            errs.append(f"[{cid}] invocation.type 잘못됨: {itype!r} (via 아님, type 사용)")
            continue
        for field in INVOCATION_REQUIRED[itype]:
            if field not in inv:
                errs.append(f"[{cid}] invocation({itype})에 {field!r} 없음")
        if runtime in RUNTIMES and itype != runtime and runtime not in ("skill", "graphql"):
            errs.append(f"[{cid}] invocation.type({itype}) ≠ plugin.runtime({runtime})")
    return errs


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    files = sorted((root / "examples").glob("*.json"))
    if not files:
        print("examples/*.json 없음", file=sys.stderr)
        return 1
    total_err = 0
    for f in files:
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"FAIL {f.name}: JSON 파싱 실패 {e}")
            total_err += 1
            continue
        errs = validate_manifest(m)
        if errs:
            total_err += len(errs)
            print(f"FAIL {f.name}:")
            for e in errs:
                print(f"    - {e}")
        else:
            print(f"OK   {f.name}")
    print(f"\n{len(files)}개 파일 · 오류 {total_err}건")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
