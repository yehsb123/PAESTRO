# ingest — 오프라인 소스 → 매니페스트 변환기

외부 소스를 PAESTRO Capability 매니페스트로 정규화하는 **빌드타임 카탈로그 생산기**.
실행(runtime)은 엔진이, 여기선 매니페스트만 만든다. (`tools/scan.js` = VS Code판, 여기 = REST판)

## OpenAPI(REST)

```bash
python ingest/openapi_to_manifest.py --in ingest/sample_openapi.json --plugin petstore --out ingest/out
```

- 오퍼레이션(path+method) 1개 → capability 1개
- `side_effects`: HTTP 메서드 기반(GET=read_only, DELETE=irreversible, 그 외=reversible)
- 출력은 `schemas/validate.py` 계약을 통과 → 엔진 `/index`에 투입 가능
- 의존성 0(stdlib)

## 로드맵
- [x] OpenAPI → 매니페스트
- [ ] MCP 서버 tool 목록 → 매니페스트 (다음)
