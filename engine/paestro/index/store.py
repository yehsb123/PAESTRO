"""[3] 색인 저장소 — ChromaDB 래퍼.

capability를 임베딩해 upsert하고 의미 검색으로 top-k를 돌려준다.
Chroma 메타는 스칼라만 허용 → invocation(dict)은 직렬화해 저장.
"""
from __future__ import annotations

from typing import Any

import chromadb

from . import embedding

_client = chromadb.PersistentClient(path=".chroma")
_col = _client.get_or_create_collection("capabilities", metadata={"hnsw:space": "cosine"})


def upsert(caps: list[dict[str, Any]]) -> int:
    if not caps:
        return 0
    # id 중복 제거(확장 다중 버전 설치 등) — 마지막 것 유지. Chroma는 unique id 요구.
    caps = list({c["id"]: c for c in caps}.values())
    metas = [
        {
            "plugin": c.get("plugin", ""),
            "runtime": c.get("runtime", "vscode"),
            "intent": c.get("intent", ""),
            "side_effects": c.get("side_effects", "read_only"),
            "invocation": str(c.get("invocation", {})),
        }
        for c in caps
    ]
    _col.upsert(
        ids=[c["id"] for c in caps],
        embeddings=embedding.embed_passages([c["embedding_text"] for c in caps]),
        documents=[c["embedding_text"] for c in caps],
        metadatas=metas,
    )
    return len(caps)


_LEX_WEIGHT = 0.4  # 하이브리드: dense(임베딩) + LEX_WEIGHT * lexical(토큰 겹침)


def query(text: str, k: int = 5) -> list[dict[str, Any]]:
    # 넉넉히 뽑아(dense) 렉시컬 겹침으로 재랭크 → 소형 다국어 모델의 KO 약점 보완.
    pool = max(k * 6, 30)
    res = _col.query(
        query_embeddings=[embedding.embed_query(text)],
        n_results=pool,
        include=["metadatas", "documents", "distances"],
    )
    ids = res.get("ids", [[]])[0]
    metas = res["metadatas"][0]
    docs = res.get("documents", [[]])[0]
    dists = res["distances"][0]

    qtokens = [t for t in text.lower().split() if len(t) >= 2]
    scored: list[tuple[float, int]] = []
    for i in range(len(ids)):
        doc = f"{(docs[i] or '')} {metas[i].get('intent', '')}".lower()
        lex = (sum(1 for t in qtokens if t in doc) / len(qtokens)) if qtokens else 0.0
        dense = 1.0 - float(dists[i])  # cosine distance → similarity
        scored.append((dense + _LEX_WEIGHT * lex, i))
    scored.sort(reverse=True)

    hits: list[dict[str, Any]] = []
    for score, i in scored[:k]:
        m = metas[i]
        hits.append(
            {
                "id": ids[i],
                "intent": m.get("intent"),
                "plugin": m.get("plugin"),
                "side_effects": m.get("side_effects"),
                "invocation": m.get("invocation"),
                "distance": dists[i],
                "score": round(score, 4),
            }
        )
    return hits


def count() -> int:
    return _col.count()
