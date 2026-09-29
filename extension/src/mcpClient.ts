// MCP stdio 클라이언트. vscode 비의존이라 헤드리스 테스트가 된다.
// stdio 전송은 줄 단위 JSON-RPC 다. initialize 핸드셰이크 뒤 tools/call 을 부른다.
import { spawn } from "node:child_process";

export type McpResult = { ok: boolean; text: string };

export function callMcpTool(
  command: string,
  args: string[],
  tool: string,
  toolArgs: unknown,
  timeoutMs = 15000
): Promise<McpResult> {
  return new Promise((resolve) => {
    let done = false;
    const finish = (r: McpResult) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try {
        child.kill();
      } catch {
        /* 이미 종료 */
      }
      resolve(r);
    };

    const child = spawn(command, args, { stdio: ["pipe", "pipe", "pipe"] });
    const timer = setTimeout(() => finish({ ok: false, text: "MCP 시간초과" }), timeoutMs);
    child.on("error", (e) => finish({ ok: false, text: `MCP 실행 오류: ${e.message}` }));

    let idc = 0;
    const waiters = new Map<number, (m: any) => void>();
    const rpc = (method: string, params: unknown) =>
      new Promise<any>((res) => {
        const id = ++idc;
        waiters.set(id, res);
        child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
      });
    const notify = (method: string) => child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method })}\n`);

    let buf = "";
    child.stdout.on("data", (d: Buffer) => {
      buf += d.toString("utf8");
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        let msg: any;
        try {
          msg = JSON.parse(line);
        } catch {
          continue;
        }
        if (msg.id != null && waiters.has(msg.id)) {
          waiters.get(msg.id)!(msg);
          waiters.delete(msg.id);
        }
      }
    });

    (async () => {
      try {
        const init = await rpc("initialize", {
          protocolVersion: "2024-11-05",
          capabilities: {},
          clientInfo: { name: "paestro", version: "0.0.1" },
        });
        if (init.error) return finish({ ok: false, text: `MCP initialize 오류: ${init.error.message}` });
        notify("notifications/initialized");
        const r = await rpc("tools/call", { name: tool, arguments: toolArgs ?? {} });
        if (r.error) return finish({ ok: false, text: `MCP 오류: ${r.error.message ?? JSON.stringify(r.error)}` });
        const content = r.result?.content;
        const text = Array.isArray(content)
          ? content.map((c: any) => c?.text ?? JSON.stringify(c)).join("\n")
          : JSON.stringify(r.result);
        finish({ ok: true, text: String(text).slice(0, 2000) });
      } catch (e: any) {
        finish({ ok: false, text: `MCP 실패: ${e?.message ?? e}` });
      }
    })();
  });
}
