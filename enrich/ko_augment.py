"""한국어 동의어 주입 — 영어 embedding_text/keywords에 한국어를 붙여 KO 검색 개선(API 불필요).

crawl/enrich 단계에서 capability마다 호출한다. 영어 토큰이 ko_terms에 있으면 대응 한국어를
keywords와 embedding_text에 추가한다. 결정적(deterministic).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_TERMS: dict | None = None


def _load() -> dict:
    global _TERMS
    if _TERMS is None:
        raw = json.loads((Path(__file__).resolve().parent / "ko_terms.json").read_text(encoding="utf-8"))
        _TERMS = {k: v for k, v in raw.items() if not k.startswith("_")}
    return _TERMS


def augment(cap: dict) -> dict:
    terms = _load()
    text = (cap.get("embedding_text") or cap.get("intent", ""))
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)  # camelCase 분해
    toks = {t for t in re.split(r"[\s._:/!-]+", text.lower()) if t}
    ko: list[str] = []
    for en, kos in terms.items():
        if en in toks:
            ko.extend(kos)
    if ko:
        cap["keywords"] = sorted(set((cap.get("keywords") or []) + ko))
        cap["embedding_text"] = (cap.get("embedding_text", "") + " " + " ".join(ko)).strip()
    return cap
