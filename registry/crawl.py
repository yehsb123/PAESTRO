#!/usr/bin/env python3
"""PAESTRO 레지스트리 크롤러 — GitHub/웹의 실제 오픈소스 → 통합 capability 레지스트리.

registry/sources.json의 소스를 긁어(각 소스 → 알맞은 ingest 변환기) 매니페스트로 정규화하고,
safety로 side_effects를 통일 분류한 뒤 계약 검증하여 registry/catalog.json으로 합친다.

- VS Code 확장: GitHub raw package.json(+ package.nls.json) → contributes.commands
- OpenAPI: 스펙 URL → 오퍼레이션
- 실패한 소스는 건너뛴다(네트워크/브랜치 차이). 의존성 0(stdlib).

실행
  python registry/crawl.py                 # sources.json 전체
  python registry/crawl.py --limit 3       # 앞 3개 vscode만(빠른 확인)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("ingest", "schemas", "enrich"):
    sys.path.insert(0, str(ROOT / sub))

import cli_to_manifest as cli  # noqa: E402
import openapi_to_manifest as oa  # noqa: E402
import vscode_pkg_to_manifest as vs  # noqa: E402
from ko_augment import augment as ko_augment  # noqa: E402
from safety import classify_side_effects  # noqa: E402
from validate import validate_manifest  # noqa: E402

UA = {"User-Agent": "paestro-registry-crawler/0.1"}


def fetch_json(url: str, timeout: int = 25, retries: int = 2):
    last: Exception | None = None
    for _ in range(retries + 1):  # 일시적 네트워크 실패 재시도 → 크롤 안정화
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError) as e:
            last = e
    raise last if last else RuntimeError("fetch 실패")


def fetch_vscode(repo: str):
    """main/master 순으로 package.json(+nls) 시도."""
    for branch in ("main", "master"):
        base = f"https://raw.githubusercontent.com/{repo}/{branch}"
        try:
            pkg = fetch_json(f"{base}/package.json")
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
            continue
        nls = {}
        try:
            nls = fetch_json(f"{base}/package.nls.json")
        except Exception:
            pass
        return pkg, nls
    return None, None


def crawl_apiguru(providers: list[str], cap: int):
    """apis.guru(수천 개 실제 OpenAPI 디렉토리)에서 지정 provider 스펙 크롤 → REST 매니페스트."""
    idx = fetch_json("https://api.apis.guru/v2/list.json", timeout=40)
    out = []
    for prov in providers:
        entry = idx.get(prov)
        if not entry:
            continue
        vs = entry.get("versions", {})
        ver = vs.get(entry.get("preferred")) or (next(iter(vs.values()), {}) if vs else {})
        url = ver.get("swaggerUrl")
        if not url:
            continue
        try:
            spec = fetch_json(url, timeout=40)
        except Exception:
            continue
        m = oa.convert(spec, re.sub(r"[^A-Za-z0-9]", "", prov.split(".")[0]), "")
        m["capabilities"] = m["capabilities"][:cap]
        if m["capabilities"]:
            out.append((prov, m))
    return out


def crawl_mcp(url: str, limit: int) -> dict:
    """공식 MCP 레지스트리에서 서버 목록 크롤 → 서버 단위 capability(계층 라우팅용)."""
    servers, cursor = [], None
    while len(servers) < limit:
        u = url + "?limit=50" + (f"&cursor={cursor}" if cursor else "")
        try:
            data = fetch_json(u)
        except Exception:
            break
        batch = data.get("servers", [])
        if not batch:
            break
        servers.extend(batch)
        meta = data.get("metadata") or {}
        cursor = meta.get("next_cursor") or meta.get("nextCursor")
        if not cursor:
            break
    caps, seen = [], set()
    for s in servers[:limit]:
        srv = s.get("server", s)
        name = srv.get("name", "")
        if not name or name in seen:
            continue
        seen.add(name)
        desc = srv.get("description") or srv.get("title") or name
        caps.append({
            "id": "mcp." + re.sub(r"[^A-Za-z0-9._-]", "-", name),
            "intent": desc[:120],
            "keywords": [],
            "when_to_use": "",
            "when_not_to_use": "",
            "invocation": {"type": "mcp", "server": name, "tool": "*"},
            "inputs": {},
            "side_effects": "read_only",
            "embedding_text": f"{srv.get('title', '')} {desc} {name}".strip(),
        })
    return {
        "plugin": {"id": "mcp.registry", "displayName": "MCP Registry", "version": "0",
                   "runtime": "mcp", "source": {"kind": "mcp-manifest"},
                   "auth": {"type": "none"}, "sandbox": "recommended"},
        "capabilities": caps,
    }


def enrich_safety(manifest: dict) -> dict:
    for c in manifest["capabilities"]:
        c["side_effects"] = classify_side_effects(c.get("embedding_text") or c.get("intent", ""))
        ko_augment(c)  # 한국어 동의어 주입 → KO 검색 개선
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="vscode 소스 앞 N개만")
    ap.add_argument("--out", default="registry/catalog.json")
    args = ap.parse_args()

    sources = json.loads((ROOT / "registry" / "sources.json").read_text(encoding="utf-8"))
    manifests, rows = [], []

    vlist = sources.get("vscode", [])
    if args.limit:
        vlist = vlist[: args.limit]
    for s in vlist:
        pkg, nls = fetch_vscode(s["repo"])
        if not pkg:
            rows.append((f"vscode:{s['name']}", "FETCH FAIL", 0))
            continue
        m = enrich_safety(vs.convert(pkg, nls, plugin=f"vscode.{s['name']}"))
        ok = not validate_manifest(m)
        rows.append((f"vscode:{s['name']}", "OK" if ok else "INVALID", len(m["capabilities"])))
        if ok:
            manifests.append(m)

    for s in sources.get("openapi", []):
        try:
            spec = fetch_json(s["url"])
            m = enrich_safety(oa.convert(spec, s["name"], ""))
            ok = not validate_manifest(m)
            rows.append((f"openapi:{s['name']}", "OK" if ok else "INVALID", len(m["capabilities"])))
            if ok:
                manifests.append(m)
        except Exception as e:
            rows.append((f"openapi:{s['name']}", f"FAIL {type(e).__name__}", 0))

    cli_cfg = sources.get("cli")
    if cli_cfg and cli_cfg.get("dir"):
        cdir = ROOT / cli_cfg["dir"]
        for f in sorted(cdir.glob("*.txt")) if cdir.exists() else []:
            name = f.stem
            subs = cli.parse_subcommands(f.read_text(encoding="utf-8", errors="replace"))
            if not subs:
                rows.append((f"cli:{name}", "no-commands", 0))
                continue
            m = enrich_safety(cli.convert(subs, name, name))
            ok = not validate_manifest(m)
            rows.append((f"cli:{name}", "OK" if ok else "INVALID", len(m["capabilities"])))
            if ok:
                manifests.append(m)

    ag = sources.get("apiguru")
    if ag and ag.get("providers"):
        try:
            for prov, m in crawl_apiguru(ag["providers"], ag.get("cap", 30)):
                m = enrich_safety(m)
                ok = not validate_manifest(m)
                rows.append((f"apiguru:{prov}", "OK" if ok else "INVALID", len(m["capabilities"])))
                if ok:
                    manifests.append(m)
        except Exception as e:
            rows.append(("apiguru", f"FAIL {type(e).__name__}", 0))

    mcp_cfg = sources.get("mcp")
    if mcp_cfg and mcp_cfg.get("url"):
        try:
            m = enrich_safety(crawl_mcp(mcp_cfg["url"], mcp_cfg.get("limit", 50)))
            ok = not validate_manifest(m)
            rows.append(("mcp:registry", "OK" if ok else "INVALID", len(m["capabilities"])))
            if ok:
                manifests.append(m)
        except Exception as e:
            rows.append(("mcp:registry", f"FAIL {type(e).__name__}", 0))

    all_caps = [c for m in manifests for c in m["capabilities"]]
    out = ROOT / args.out
    out.write_text(json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf-8")

    print("소스                     상태          caps")
    print("-" * 46)
    for name, status, n in rows:
        print(f"{name:24} {status:12} {n:5}")
    se: dict[str, int] = {}
    for c in all_caps:
        se[c["side_effects"]] = se.get(c["side_effects"], 0) + 1
    print("-" * 46)
    print(f"플러그인 {len(manifests)}개 · capability {len(all_caps)}개 · side_effects {se}")
    print(f"→ {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
