#!/usr/bin/env python3
"""CLI --help 텍스트 → PAESTRO Capability 매니페스트 (오프라인 인제스트, 의존성 0).

git/docker/npm/kubectl 류의 `--help`에서 서브커맨드 목록(Commands 섹션)을 파싱해
서브커맨드 하나를 capability 하나로 정규화한다. `--help`는 비정형이라 best-effort.

입력  help 텍스트 파일(예: `git --help > git_help.txt`)
실행
  python ingest/cli_to_manifest.py --in ingest/sample_cli_help.txt --plugin git --out ingest/out
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

_HEADER = re.compile(r"^\s*(available\s+)?(sub)?commands:?\s*$", re.I)
_OTHER_HEADER = re.compile(r"^\S.*:\s*$")  # 'Options:', 'Flags:' 등 다른 섹션 시작
_ROW = re.compile(r"^\s+([a-zA-Z][\w:-]*)\s{2,}(\S.*)$")

_DESTRUCTIVE = re.compile(r"\b(delete|remove|rm|reset|revert|prune|drop|destroy|push|clean|uninstall|deploy)\b", re.I)
_READONLY = re.compile(r"\b(list|ls|show|get|status|log|view|describe|inspect|search|diff|info)\b", re.I)


def classify(name: str, desc: str) -> str:
    text = f"{name} {desc}"
    if _DESTRUCTIVE.search(text):
        return "irreversible"
    if _READONLY.search(text):
        return "read_only"
    return "reversible"


def parse_subcommands(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    rows: list[tuple[str, str]] = []
    in_cmds = False
    for line in lines:
        if _HEADER.match(line):
            in_cmds = True
            continue
        if not in_cmds:
            continue
        if not line.strip():
            continue  # 빈 줄은 건너뛰되 섹션 유지
        if _OTHER_HEADER.match(line) and not _ROW.match(line):
            break  # 다른 섹션 시작 → 종료
        m = _ROW.match(line)
        if m:
            rows.append((m.group(1), m.group(2).strip()))
    # 중복 제거(순서 유지)
    seen, out = set(), []
    for n, d in rows:
        if n not in seen:
            seen.add(n)
            out.append((n, d))
    return out


def convert(subs: list[tuple[str, str]], plugin: str, binary: str) -> dict:
    caps = []
    for name, desc in subs:
        cid = f"cli.{plugin}." + re.sub(r"[^A-Za-z0-9._-]", "_", name)
        caps.append({
            "id": cid,
            "intent": desc,
            "keywords": sorted({name.lower(), *re.split(r"[\s_./-]+", desc.lower())} - {""})[:8],
            "when_to_use": "",
            "when_not_to_use": "",
            "invocation": {"type": "cli", "argv_template": [binary, name]},
            "inputs": {},
            "side_effects": classify(name, desc),
            "embedding_text": f"{desc} {binary} {name}".strip(),
        })
    return {
        "plugin": {
            "id": f"cli.{plugin}",
            "displayName": plugin,
            "version": "0",
            "runtime": "cli",
            "source": {"kind": "manual"},
            "auth": {"type": "none"},
            "sandbox": "recommended",
        },
        "capabilities": caps,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--plugin", required=True, help="플러그인 이름 (예: git)")
    ap.add_argument("--bin", dest="binary", default="", help="실제 실행 바이너리(기본=plugin)")
    ap.add_argument("--out", default="ingest/out")
    args = ap.parse_args()

    text = Path(args.inp).read_text(encoding="utf-8")
    subs = parse_subcommands(text)
    manifest = convert(subs, args.plugin, args.binary or args.plugin)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"cli.{args.plugin}.manifest.json"
    import json
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    se: dict[str, int] = {}
    for c in manifest["capabilities"]:
        se[c["side_effects"]] = se.get(c["side_effects"], 0) + 1
    print(f"→ {out_path} · 서브커맨드 {len(subs)}개 · side_effects {se}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
