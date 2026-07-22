# PAESTRO

의미로 고르는 **플러그인 라우터 + 오케스트레이터**. VS Code 확장으로 동작한다.

개발자가 자연어로 시키면, PAESTRO가 Chroma에서 관련 도구(VS Code 확장 명령 · MCP · REST · CLI)를 찾아 **번호가 붙은 후보 목록**으로 띄운다. 사용자가 `1, 2, 3, 4…` 중 고르면 실행하고, `5`는 직접 지정/설정.

```
1. Ponytail            — 개발에 유리
2. vscode.eslint.fixAll — 린트 자동 수정
3. editor.formatDocument — 포맷팅
5. 직접 지정 / 설정…
```

## 구조

```
schemas/    capability-manifest.schema.json   # 모든 어댑터의 출력 계약
examples/   vscode.eslint.manifest.json       # 정규화 예시
```

검색 단위는 플러그인이 아니라 개별 **capability**. 검색용 메타(intent·keywords)와 실행용 메타(`invocation`)를 한 문서에 담는다.
