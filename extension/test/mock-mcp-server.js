// 테스트용 MCP stdio mock. 줄 단위 JSON-RPC로 initialize·tools/call(echo)에 응답한다.
let buf = "";
process.stdin.on("data", (d) => {
  buf += d.toString("utf8");
  let nl;
  while ((nl = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (!line) continue;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      continue;
    }
    if (msg.method === "initialize") {
      reply(msg.id, { protocolVersion: "2024-11-05", capabilities: {}, serverInfo: { name: "mock", version: "0" } });
    } else if (msg.method === "tools/call") {
      const arg = JSON.stringify(msg.params?.arguments ?? {});
      reply(msg.id, { content: [{ type: "text", text: `echo:${msg.params?.name}:${arg}` }] });
    }
    // notifications(id 없음)는 무시
  }
});
function reply(id, result) {
  process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, result }) + "\n");
}
