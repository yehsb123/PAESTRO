# enrich — #2 어댑터 LLM 보강 배치

parse 단계(`tools/scan.js`)가 뽑은 뼈대 카탈로그를 받아 capability마다
`when_to_use · when_not_to_use · keywords · side_effects · args_schema`를 채운다.
**side_effects 재분류로 확장의 승인 게이트(irreversible)가 실재화**된다.

## 실행

```bash
# API 없이 규칙 기반 (안전 게이트 즉시 실재화)
python enrich/enrich.py --in enrich/sample_catalog.json --out enrich/out --heuristic

# Claude 고품질 보강 (BYO 키)
export ANTHROPIC_API_KEY=...            # Windows: set ANTHROPIC_API_KEY=...
pip install -r enrich/requirements.txt
python enrich/enrich.py --in catalog.json --out enrich/out
```

- 모델: `PAESTRO_ENRICH_MODEL`(기본 `claude-sonnet-5`, 최고 품질 `claude-opus-4-8`) · 배치 `PAESTRO_ENRICH_BATCH`(기본 15)
- 입력: `scan.js`의 중첩 manifest 배열 또는 flat capability 배열 모두 허용
- 출력: `out/enriched_catalog.json` — flat capability 배열 → 엔진 `/index`에 바로 투입 가능

## 파이프라인 위치

```
tools/scan.js (parse) → catalog.json → [enrich] → enriched_catalog.json → engine /index → Chroma
```

heuristic은 빠른 기본값·오프라인 안전망이고, LLM 보강이 검색/안전 품질을 끌어올린다. 키가 없으면 자동으로 heuristic 폴백.
