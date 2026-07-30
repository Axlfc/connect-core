import { createServer } from "http";
import * as fs from "fs";
import * as path from "path";

// Extremely simple and fast embedded web server/triage UI & MCP endpoint
const port = process.env.CODEX_MCP_PORT || 8585;

const server = createServer((req, res) => {
  // Simple router
  if (req.url === "/api/tools" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      tools: [
        {
          name: "execute-scan",
          description: "Runs a custom Codex Security scanning operation."
        },
        {
          name: "triage-finding",
          description: "Marks a finding's triage state (e.g. false_positive, verified)."
        }
      ]
    }));
  } else {
    // Return embedded simple HTML for triage and MCP tools display
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Codex Security MCP & Triage Workbench UI</title>
        <style>
          body { font-family: sans-serif; margin: 40px; background: #f9f9f9; color: #333; }
          header { background: #333; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
          .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
          table { width: 100%; border-collapse: collapse; margin-top: 10px; }
          th, td { padding: 12px; border-bottom: 1px solid #ddd; text-align: left; }
          th { background: #f2f2f2; }
          .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: bold; }
          .badge.high { background: #fee2e2; color: #991b1b; }
          .badge.med { background: #fef3c7; color: #92400e; }
        </style>
      </head>
      <body>
        <header>
          <h1>Codex Security - Embedded Triage Web UI</h1>
          <p>Model Context Protocol Server running on port ${port}</p>
        </header>
        <div class="card">
          <h2>Findings Triage Workspace</h2>
          <table>
            <thead>
              <tr>
                <th>CWE</th>
                <th>File Path</th>
                <th>Line</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>CWE-79</td>
                <td>src/app.py</td>
                <td>12</td>
                <td><span class="badge high">HIGH</span></td>
                <td><span class="badge med">PENDING</span></td>
                <td><button onclick="alert('Marked as False Positive')">False Positive</button> <button onclick="alert('Remediated!')">Remediate</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </body>
      </html>
    `);
  }
});

server.listen(port, () => {
  console.log(`[MCP SERVER] Embedded Triage Web UI & MCP server listening on http://localhost:${port}`);
});
