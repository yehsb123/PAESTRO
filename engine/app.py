"""PAESTRO 엔진 사이드카 — FastAPI 진입점.

색인·검색은 paestro.index, 오케스트레이션은 paestro.orchestrator 로 이관됨.
확장(TS)이 localhost HTTP로 호출한다:
    POST /index       capability 배열 → Chroma 색인
    POST /retrieve    { query, k } → top-k (검색만)
    POST /orchestrate { query, k } → 오케스트레이터 후보 (스파이크: 검색과 동일, 이후 확장)
    GET  /health

실행 (engine/ 디렉토리에서):
    python -m venv .venv
    .venv\\Scripts\\activate            # (mac/linux: source .venv/bin/activate)
    pip install -r requirements.txt
    uvicorn app:app --host 127.0.0.1 --port 8756
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from paestro.index import embedding, store
from paestro.orchestrator import pipeline

app = FastAPI(title="PAESTRO Engine", version="0.1.0")


class Capability(BaseModel):
    id: str
    plugin: str
    runtime: str = "vscode"
    intent: str = ""
    embedding_text: str
    side_effects: str = "read_only"
    invocation: dict[str, Any] = {}


class IndexReq(BaseModel):
    capabilities: list[Capability]


class QueryReq(BaseModel):
    query: str
    k: int = 5


@app.post("/index")
def index(req: IndexReq) -> dict[str, int]:
    n = store.upsert([c.model_dump() for c in req.capabilities])
    return {"indexed": n, "total": store.count()}


@app.post("/retrieve")
def retrieve(req: QueryReq) -> dict[str, list[dict[str, Any]]]:
    return {"hits": store.query(req.query, req.k)}


@app.post("/orchestrate")
def orchestrate(req: QueryReq) -> dict[str, Any]:
    return pipeline.orchestrate(req.query, req.k)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "model": embedding.MODEL, "count": store.count()}
