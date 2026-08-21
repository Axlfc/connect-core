import { createServer } from "http";
import * as fs from "fs";
import * as path from "path";

// [DEPRECATION NOTICE]
// This bundled plugin MCP server implementation is DEPRECATED.
// Please migrate to the canonical MCP server in `very-simplified-stack/cognito-backend/app/services/mcp_server.py`.
console.warn("[DEPRECATION WARNING] sdk/typescript/_bundled_plugin/mcp/server.mjs is deprecated.");
console.warn("[DEPRECATION WARNING] Use the canonical MCP server in 'very-simplified-stack/cognito-backend/app/services/mcp_server.py'.");

const port = process.env.CODEX_MCP_PORT || 8585;

const server = createServer((req, res) => {
  // Simple router
  if (req.url === "/api/tools" && req.method === "GET") {
    res.writeHead(200, {
      "Content-Type": "application/json",
      "X-Deprecation-Notice": "Migrate to app/services/mcp_server.py in cognito-backend"
    });
    res.end(JSON.stringify({
      deprecated: true,
      canonical_mcp_server: "very-simplified-stack/cognito-backend/app/services/mcp_server.py",
      tools: [
        {
          name: "execute-scan",
          description: "Runs a custom Codex Security scanning operation (Deprecated)."
        },
        {
          name: "triage-finding",
          description: "Marks a finding's triage state (Deprecated)."
        }
      ]
    }));
  } else {
    // Return embedded simple HTML with deprecation banner
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Codex Security MCP (DEPRECATED)</title>
        <style>
          body { font-family: sans-serif; margin: 40px; background: #f9f9f9; color: #333; }
          header { background: #b91c1c; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
          .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
          .warning { background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px; margin-bottom: 20px; }
        </style>
      </head>
      <body>
        <header>
          <h1>[DEPRECATED] Codex Security - Bundled MCP UI</h1>
          <p>This implementation has been unified into the canonical Cognito MCP Server.</p>
        </header>
        <div class="warning">
          <strong>Deprecation Notice:</strong> This JS server is deprecated. Please use <code>very-simplified-stack/cognito-backend/app/services/mcp_server.py</code>.
        </div>
      </body>
      </html>
    `);
  }
});

server.listen(port, () => {
  console.log(`[MCP SERVER DEPRECATED] Listening on http://localhost:${port}`);
});
