# registry — 팀 공유 capability 레지스트리 [6. 거버넌스]

GitHub/웹의 **실제 오픈소스**를 크롤링해 하나의 통합 capability 레지스트리로 만든다.

## 크롤

```bash
python registry/crawl.py            # sources.json 전체
python registry/crawl.py --limit 3  # 앞 3개만(빠른 확인)
```

- `sources.json` — 크롤 대상(VS Code 확장 repo, OpenAPI 스펙 URL). 자유롭게 추가.
- 각 소스 → 알맞은 `ingest/` 변환기 → `safety`로 side_effects 통일 분류 → `schemas/validate.py` 계약 검증 → `catalog.json` 합본.
- 실패한 소스(브랜치 차이·네트워크)는 건너뛰고 보고. 의존성 0(stdlib).

## 현재 seed (`catalog.json`)

실제 크롤 결과 — **8 플러그인 · 996 capability** (VS Code 확장 7 + Swagger REST):

| 소스 | capability |
|---|---|
| gitlens | 914 |
| python | 23 |
| rest-client · petstore(REST) | 19 · 19 |
| gitgraph | 10 |
| eslint · vim · prettier | 6 · 3 · 2 |

- side_effects: read_only 791 · reversible 140 · **irreversible 65**(승인 게이트 대상)
- VS Code 명령의 메뉴 컨텍스트/앵커 변형(`:editor/title`, `!account`)은 base 명령으로 통합(dedupe)해 노이즈 제거.

## 다음
- MCP 서버 목록 크롤(awesome-mcp 등) 추가
- LLM 보강(`enrich/`)으로 `when_to_use`·`keywords` 채워 검색 품질↑
- 엔진 `/index`에 투입해 실검색 정확도 측정(`eval/`)
