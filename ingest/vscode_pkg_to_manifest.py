#!/usr/bin/env python3
"""VS Code 확장 package.json → PAESTRO Capability 매니페스트 (오프라인, 의존성 0).

GitHub에서 받은 확장의 package.json(contributes.commands)을 매니페스트로 정규화한다.
%nls.key% 형태의 제목은 함께 받은 package.nls.json으로 치환한다(있으면).

tools/scan.js(로컬 스캔)와 같은 계약이지만, 이쪽은 '크롤링한 package.json 1개'를 입력으로 받는다.
"""
from __future__ import annotations

import re


def _nls(s, nls: dict):
    if isinstance(s, str) and s.startswith("%") and s.endswith("%"):
        return nls.get(s[1:-1], s[1:-1])  # 못 찾으면 키 이름이라도(사람이 읽을 수 있게)
    return s


def convert(pkg: dict, nls: dict | None = None, plugin: str | None = None) -> dict:
    nls = nls or {}
    name = str(pkg.get("name", ""))
    short = re.sub(r"^vscode-", "", name)
    pid = plugin or f"vscode.{short or name or 'unknown'}"
    cmds = ((pkg.get("contributes") or {}).get("commands")) or []

    caps = []
    seen_base: set[str] = set()
    for c in cmds:
        cmd = c.get("command")
        if not cmd:
            continue
        # 메뉴 컨텍스트/앵커 변형(gitlens.diffWithNext:editor/title, showSettingsPage!account 등)
        # → base 명령으로 통합(dedupe). ':'·'!' 첫 등장에서 자른다.
        base = re.split(r"[:!]", cmd, 1)[0]
        if base in seen_base:
            continue
        seen_base.add(base)
        cmd = base
        title = _nls(c.get("title"), nls) or cmd
        category = _nls(c.get("category"), nls) or ""
        caps.append({
            "id": f"vscode.{cmd}",
            "intent": title,
            "keywords": sorted({*(category.lower().split() if category else []),
                                *re.split(r"[\s._:/-]+", cmd.lower())} - {""})[:8],
            "when_to_use": "",
            "when_not_to_use": "",
            "invocation": {"type": "vscode", "command": cmd},
            "inputs": {},
            "side_effects": "read_only",  # crawl.py가 safety로 재분류
            "embedding_text": " ".join(x for x in [title, category, cmd] if x),
        })
    return {
        "plugin": {
            "id": pid,
            "displayName": pkg.get("displayName") or name,
            "version": str(pkg.get("version", "0")),
            "runtime": "vscode",
            "source": {"kind": "marketplace",
                       "uri": f"{pkg.get('publisher', '?')}.{name}",
                       "extractedBy": "vscode-pkg-crawler@0.1"},
            "auth": {"type": "none"},
            "sandbox": "none",
        },
        "capabilities": caps,
    }
