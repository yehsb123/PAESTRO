// MCP stdio 클라이언트 헤드리스 테스트. mock 서버를 띄워 initialize·tools/call 왕복을 확인한다.
// 실행: npm run test:mcp  (mcpClient.ts 를 test/_mcpClient.cjs 로 번들한 뒤 이 파일을 돌린다)
const path = require("node:path");
const { callMcpTool } = require("./_mcpClient.cjs");

(async () => {
  const mock = path.join(__dirname, "mock-mcp-server.js");
  const r = await callMcpTool("node", [mock], "create_issue", { title: "hi" });
  const pass = r.ok && r.text.includes("echo:create_issue") && r.text.includes("hi");
  console.log(`ok=${r.ok} text=${r.text}`);
  console.log(pass ? "MCP TEST PASS" : "MCP TEST FAIL");
  process.exit(pass ? 0 : 1);
})();
