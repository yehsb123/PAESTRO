// [1] 인터페이스 — 엔진 사이드카 HTTP 클라이언트.
// extension.ts 의 인라인 fetch 가 이리로 이관된다.

const ENGINE = "http://127.0.0.1:8756";

export interface Hit {
  id: string;
  intent: string;
  plugin: string;
  side_effects: string;
  invocation: string;
  distance: number;
}

export async function index(capabilities: Array<Record<string, unknown>>): Promise<{ indexed: number; total: number }> {
  const res = await fetch(`${ENGINE}/index`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ capabilities }),
  });
  return res.json() as Promise<{ indexed: number; total: number }>;
}

export async function retrieve(query: string, k = 5): Promise<Hit[]> {
  const res = await fetch(`${ENGINE}/retrieve`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query, k }),
  });
  const json = (await res.json()) as { hits: Hit[] };
  return json.hits ?? [];
}

export async function health(): Promise<boolean> {
  try {
    const res = await fetch(`${ENGINE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
