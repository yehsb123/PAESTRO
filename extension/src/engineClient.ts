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

export interface Chosen extends Hit {
  needs_approval: boolean;
}
export interface Step {
  n: number;
  step: string;
  chosen: Chosen | null;
  alternatives: Hit[];
}
export interface Plan {
  query: string;
  multi_step: boolean;
  steps: Step[];
  needs_approval: number;
}

// [4] 오케스트레이터 — 복합 요구 → 멀티스텝 실행 계획.
export async function orchestrate(query: string, k = 3): Promise<Plan> {
  const res = await fetch(`${ENGINE}/orchestrate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query, k }),
  });
  return (await res.json()) as Plan;
}

export async function health(): Promise<boolean> {
  try {
    const res = await fetch(`${ENGINE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
