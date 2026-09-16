"""[3] 색인 저장소 — ChromaDB 래퍼.

capability를 임베딩해 upsert하고 의미 검색으로 top-k를 돌려준다.
Chroma 메타는 스칼라만 허용 → invocation(dict)은 직렬화해 저장.
"""
from __future__ import annotations

import json
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
            "invocation": json.dumps(c.get("invocation", {}), ensure_ascii=False),
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
_PHRASE_WEIGHT = 0.5  # 질의 전체가 문서에 연속 부분문자열로 나타날 때 보너스
_LEX_TERMS = 5  # lexical 리콜 서브쿼리에 쓸 질의 토큰 최대 수


def _collect(emb: list[float], n: int, where_document: dict | None,
             cand: dict[str, tuple]) -> None:
    """dense 근접 결과를 후보 dict에 병합(id 기준, 최초 거리 유지)."""
    kw: dict[str, Any] = {"query_embeddings": [emb], "n_results": n,
                          "include": ["metadatas", "documents", "distances"]}
    if where_document:
        kw["where_document"] = where_document
    res = _col.query(**kw)
    ids = res.get("ids", [[]])[0]
    metas = res["metadatas"][0]
    docs = res.get("documents", [[]])[0]
    dists = res["distances"][0]
    for i in range(len(ids)):
        cand.setdefault(ids[i], (metas[i], docs[i], dists[i]))


def query(text: str, k: int = 5) -> list[dict[str, Any]]:
    # 하이브리드 리콜: (1) dense 풀 + (2) lexical 리콜(질의 토큰을 포함하는 문서를
    # 실거리와 함께 별도로 끌어옴) → 합집합 재랭크. 소형 다국어 모델이 음차/한글을
    # 크게 놓쳐(dense 랭크 수백 위) 정확 키워드 매치가 dense 풀에 못 드는 문제를 구제.
    emb = embedding.embed_query(text)
    pool = max(k * 6, 30)
    cand: dict[str, tuple] = {}
    _collect(emb, pool, None, cand)  # (1) dense 리콜

    # (2) lexical 리콜 — 대소문자 보존 위해 원문 토큰으로 $contains
    raw_tokens = [t for t in text.split() if len(t) >= 2]
    terms = raw_tokens[:_LEX_TERMS]
    # (2a-phrase) 질의 구절 전체를 연속 부분문자열로 포함하는 문서를 직접 리콜.
    #      정답이 dense로 크게 밀리고(rank 100+) 형제들이 개별 토큰을 나눠 가져
    #      토큰/AND 채널까지 다 차지할 때, 연속 구절 매치 문서를 확실히 풀에 넣음.
    stripped = text.strip()
    if len(terms) >= 2 and " " in stripped:
        try:
            _collect(emb, 10, {"$contains": stripped}, cand)
        except Exception:
            pass
    # (2b-AND) 모든 토큰을 동시에 포함하는 문서(AND) — 완전 렉시컬 매치를 직접 리콜.
    #      흔한 토큰('저장소'·'목록')이라 토큰별 dense-top-N 밖으로 밀리는 정답을 구제.
    if len(terms) >= 2:
        try:
            _collect(emb, 10, {"$and": [{"$contains": t} for t in terms]}, cand)
        except Exception:
            pass
    # (2b) 토큰별 리콜(부분 매치 커버)
    for t in terms:
        try:
            _collect(emb, 15, {"$contains": t}, cand)
        except Exception:
            pass  # 필터 미지원/빈 결과는 무시(dense 풀로 폴백)

    qtokens = [t.lower() for t in raw_tokens]
    phrase = text.strip().lower()
    scored: list[tuple[float, str, dict, float]] = []
    for cid, (meta, doc, dist) in cand.items():
        d = f"{(doc or '')} {meta.get('intent', '')}".lower()
        lex = (sum(1 for t in qtokens if t in d) / len(qtokens)) if qtokens else 0.0
        # 연속 구절 매치 보너스 — overlay 키워드는 문서에 연속 구절로 저장됨. 형제 명령이
        # 흩어진 토큰으로 lex 1.0을 동점받을 때, 질의를 통째로 담은 정답을 변별.
        phrase_hit = 1.0 if len(qtokens) >= 2 and phrase in d else 0.0
        dense = 1.0 - float(dist)  # cosine distance → similarity
        scored.append((dense + _LEX_WEIGHT * lex + _PHRASE_WEIGHT * phrase_hit, cid, meta, dist))
    scored.sort(key=lambda x: x[0], reverse=True)

    hits: list[dict[str, Any]] = []
    for score, cid, m, dist in scored[:k]:
        hits.append(
            {
                "id": cid,
                "intent": m.get("intent"),
                "plugin": m.get("plugin"),
                "side_effects": m.get("side_effects"),
                "invocation": m.get("invocation"),
                "distance": dist,
                "score": round(score, 4),
            }
        )
    return hits


def count() -> int:
    return _col.count()
