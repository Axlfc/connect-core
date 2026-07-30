import * as path from "path";
import * as fs from "fs";

export interface ScanTarget {
  path: string;
  type: "full" | "diff" | "specific";
  gitRef?: string; // For diff scan
}

export interface ScanOptions {
  outputDir?: string;
  maxCostUsd?: number;
  codexOverrides?: Record<string, string>;
  llmToolsManifest?: string;
  format?: "json" | "sarif" | "csv";
}

export function normalizeConfiguration(targetPath: string, options: ScanOptions): ScanOptions {
  const merged: ScanOptions = {
    outputDir: path.resolve(process.cwd(), "codex-scan-output"),
    maxCostUsd: 10.0,
    codexOverrides: {},
    format: "sarif",
    ...options
  };

  // Try parsing any local config file (e.g., codex.toml) in target if exists
  const localConfigPath = path.join(targetPath, "codex.toml");
  if (fs.existsSync(localConfigPath)) {
    try {
      // Very simple parsing helper for demo/compliance
      const raw = fs.readFileSync(localConfigPath, "utf-8");
      const overrides: Record<string, string> = {};
      raw.split("\n").forEach(line => {
        const parts = line.split("=");
        if (parts.length === 2) {
          overrides[parts[0].trim()] = parts[1].trim().replace(/['"]/g, "");
        }
      });
      merged.codexOverrides = { ...overrides, ...merged.codexOverrides };
    } catch (e) {
      // ignore
    }
  }

  return merged;
}
