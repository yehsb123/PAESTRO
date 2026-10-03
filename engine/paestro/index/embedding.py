"""[3] 임베딩 — fastembed 다국어 모델.

paraphrase-multilingual-mpnet-base-v2: 다국어(한/영 포함 50+ 언어).
한국어 질의로 영어 title capability를 찾는 것이 목표다(PoC의 KO-EN 단절 해결).
e5 계열과 달리 passage:/query: 접두사가 필요 없다.

lazy_load=True: 모델 로드(약 1.3GB)를 첫 임베딩까지 미룬다. 엔진이 떠 있어도
검색 전(startup, /health, 색인 전 대기)에는 메모리를 잡지 않는다.
"""
from __future__ import annotations

from fastembed import TextEmbedding

MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
_embedder = TextEmbedding(model_name=MODEL, lazy_load=True)


def _embed(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _embedder.embed(texts)]


def embed_passages(texts: list[str]) -> list[list[float]]:
    return _embed(texts)


def embed_query(text: str) -> list[float]:
    return _embed([text])[0]
