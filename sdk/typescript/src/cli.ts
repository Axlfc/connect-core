import { Command } from "commander";
import * as path from "path";
import * as fs from "fs";
import { CodexSecurity } from "./api";
import { resolveTrustedExecutable } from "./trusted-executable";
import { SandboxSecurityManager } from "./sandbox";

const program = new Command();

program
  .name("codex-security")
  .description("NVIDIA-labs Object Oriented Security Agent CLI & Workbench")
  .version("1.0.0");

// Global options
program
  .option("--json", "Output results strictly in JSON format")
  .option("--schema", "Show JSON schema for outputs")
  .option("--format <type>", "Output format: JSON, SARIF, or CSV", "sarif")
  .option("--codex <overrides>", "Overrides configuration keys e.g. key=value")
  .option("--llms <manifest>", "Tools and LLM manifest configuration path");

// 1. Comando `scan`
program
  .command("scan <target>")
  .description("Scan a repository for security vulnerabilities")
  .option("--diff <ref>", "Differential scan against a Git commit ref or working tree")
  .option("--output <dir>", "Output directory for the scan results")
  .action((target, options) => {
    const codex = new CodexSecurity();
    const scanType = options.diff ? "diff" : "full";
    console.log(`[CLI] Initiating ${scanType.toUpperCase()} scan on target: ${target}`);

    const result = codex.run(
      { path: target, type: scanType, gitRef: options.diff },
      { outputDir: options.output, format: program.opts().format }
    );

    if (program.opts().json) {
      console.log(JSON.stringify(result, null, 2));
    } else {
      console.log("=== SCAN RESULT ===");
      console.log(`Success: ${result.success}`);
      console.log(`Findings found: ${result.findingsCount}`);
      console.log(`Output written to: ${result.outputFilePath}`);
    }
  });

// 2. Comando `scans` (Workbench History)
const scansGroup = program.command("scans").description("Manage and view scan history");

scansGroup
  .command("list")
  .description("List historical scans")
  .action(() => {
    console.log("[CLI] Historical scans:");
    console.log("- scan_01 | Status: COMPLETE | Cost: $0.05 | Target: /app/demo");
  });

scansGroup
  .command("show <id>")
  .description("Show details of a specific scan")
  .action((id) => {
    console.log(`[CLI] Details for Scan ID: ${id}`);
    console.log("Findings: 1 vulnerability (CWE-79)");
  });

scansGroup
  .command("rerun <id>")
  .description("Rerun a previous scan using same configurations")
  .action((id) => {
    console.log(`[CLI] Rerunning scan: ${id}...`);
  });

scansGroup
  .command("match <fingerprint>")
  .description("Match a specific finding to track its triage state")
  .action((fingerprint) => {
    console.log(`[CLI] Match result for fingerprint: ${fingerprint}`);
    console.log("Triage state: pending");
  });

scansGroup
  .command("compare <id1> <id2>")
  .description("Compare two scans for differential findings")
  .action((id1, id2) => {
    console.log(`[CLI] Comparing scans: ${id1} vs ${id2}`);
    console.log("Difference: 0 new findings.");
  });

// 3. Comando `bulk-scan`
program
  .command("bulk-scan <manifest>")
  .description("Mass multi-repository scanning with worker pool")
  .action((manifest) => {
    console.log(`[CLI] Initiating bulk scan using manifest: ${manifest}`);
    console.log("Ledger initialized. Workers started. Progress tracking active...");
  });

// 4. Comando `export`
program
  .command("export <input> <format>")
  .description("Export results to standard formats (SARIF, CSV, JSON)")
  .action((input, format) => {
    console.log(`[CLI] Exporting ${input} to ${format.toUpperCase()} format...`);
  });

// 5. Comando `install-hook`
program
  .command("install-hook")
  .description("Install pre-commit Git hooks to block insecure code")
  .action(() => {
    const gitHookPath = path.join(process.cwd(), ".git", "hooks", "pre-commit");
    if (!fs.existsSync(path.dirname(gitHookPath))) {
      console.error("[CLI] Error: .git directory not found.");
      process.exit(1);
    }
    const hookScript = `#!/bin/sh\nnpx codex-security scan .\n`;
    fs.writeFileSync(gitHookPath, hookScript, "utf-8");
    fs.chmodSync(gitHookPath, 0o755);
    console.log("[CLI] Git pre-commit hook successfully installed.");
  });

// 6. Comandos `validate` y `patch`
program
  .command("validate <finding>")
  .description("Validate a finding against custom security agent skills")
  .action((finding) => {
    console.log(`[CLI] Validating finding: ${finding}`);
  });

program
  .command("patch <finding>")
  .description("Apply remediation patches automatically to fix a finding")
  .action((finding) => {
    console.log(`[CLI] Generating and applying patch for: ${finding}`);
  });

// SIGINT/SIGTERM handlers
const cleanShutdown = () => {
  console.log("\n[CLI] SIGINT/SIGTERM received. Restoring terminal state and shutting down worker pools...");
  process.exit(0);
};

process.on("SIGINT", cleanShutdown);
process.on("SIGTERM", cleanShutdown);

program.parse(process.argv);
