"""PAESTRO 엔진 사이드카 — capability 색인 + 다국어 의미 검색.

VS Code 확장(TS)이 localhost HTTP로 호출한다:
    POST /index     capability 배열 → Chroma 색인
    POST /retrieve  { query, k }    → top-k capability
    GET  /health

임베딩: fastembed(ONNX, torch 불필요)의 다국어 모델 → 한국어 질의로 영어 title 확장을 찾는다
        (PoC에서 렉시컬 매칭이 못 넘던 KO↔EN 단절을 해결).
저장:   ChromaDB PersistentClient(로컬 .chroma) — 셀프호스팅.

실행:
    cd engine && python -m venv .venv
    .venv\\Scripts\\activate            # (Windows) / source .venv/bin/activate (mac·linux)
    pip install -r requirements.txt
    uvicorn app:app --host 127.0.0.1 --port 8756
"""
from __future__ import annotations

from typing import Any

import chromadb
from fastapi import FastAPI
from fastembed import TextEmbedding
from pydantic import BaseModel

MODEL = "intfloat/multilingual-e5-small"  # 다국어(한/영) 경량. 필요 시 e5-large / bge-m3 로 교체.

app = FastAPI(title="PAESTRO Engine", version="0.1.0")
_embedder = TextEmbedding(model_name=MODEL)
_client = chromadb.PersistentClient(path=".chroma")
_col = _client.get_or_create_collection("capabilities", metadata={"hnsw:space": "cosine"})


def _embed(texts: list[str], prefix: str) -> list[list[float]]:
    # e5 계열은 passage:/query: 접두사를 붙일 때 성능이 오른다.
    vecs = _embedder.embed([f"{prefix}{t}" for t in texts])
    return [v.tolist() for v in vecs]


class Capability(BaseModel):
    id: str
    plugin: str
    runtime: str = "vscode"
    intent: str
    embedding_text: str
    side_effects: str = "read_only"
    invocation: dict[str, Any] = {}


class IndexReq(BaseModel):
    capabilities: list[Capability]


class RetrieveReq(BaseModel):
    query: str
    k: int = 5


@app.post("/index")
def index(req: IndexReq) -> dict[str, int]:
    caps = req.capabilities
    if not caps:
        return {"indexed": 0, "total": _col.count()}
    metas = []
    for c in caps:
        metas.append({
            "plugin": c.plugin,
            "runtime": c.runtime,
            "intent": c.intent,
            "side_effects": c.side_effects,
            "invocation": str(c.invocation),  # Chroma 메타는 스칼라만 허용 → 직렬화
        })
    _col.upsert(
        ids=[c.id for c in caps],
        embeddings=_embed([c.embedding_text for c in caps], "passage: "),
        documents=[c.embedding_text for c in caps],
        metadatas=metas,
    )
    return {"indexed": len(caps), "total": _col.count()}


@app.post("/retrieve")
def retrieve(req: RetrieveReq) -> dict[str, list[dict[str, Any]]]:
    res = _col.query(query_embeddings=_embed([req.query], "query: "), n_results=req.k)
    hits: list[dict[str, Any]] = []
    ids = res.get("ids", [[]])[0]
    for i, cid in enumerate(ids):
        meta = res["metadatas"][0][i]
        hits.append({
            "id": cid,
            "intent": meta.get("intent"),
            "plugin": meta.get("plugin"),
            "side_effects": meta.get("side_effects"),
            "invocation": meta.get("invocation"),
            "distance": res["distances"][0][i],
        })
    return {"hits": hits}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "model": MODEL, "count": _col.count()}
