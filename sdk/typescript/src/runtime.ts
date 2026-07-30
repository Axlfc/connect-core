import { execSync } from "child_process";
import * as path from "path";
import * as fs from "fs";
import { PluginPythonUnavailableError } from "./errors";

export class PythonRuntimeBootstrap {
  private codexHome: string;

  constructor() {
    this.codexHome = process.env.CODEX_HOME || path.join(process.env.HOME || process.env.USERPROFILE || ".", ".codex-home");
  }

  public getCodexHome(): string {
    return this.codexHome;
  }

  public validatePythonVersion(): string {
    const commands = ["python3", "python"];
    for (const cmd of commands) {
      try {
        const out = execSync(`${cmd} --version`, { stdio: "pipe" }).toString().trim();
        // Extract version e.g. "Python 3.11.2"
        const match = out.match(/Python\s+(\d+)\.(\d+)/);
        if (match) {
          const major = parseInt(match[1], 10);
          const minor = parseInt(match[2], 10);
          if (major === 3 && minor >= 10) {
            return cmd;
          }
        }
      } catch (e) {
        // try next
      }
    }
    throw new PluginPythonUnavailableError("Required Python version 3.10+ not found in PATH.");
  }

  public bootstrapPlugin(): string {
    const pythonExecutable = this.validatePythonVersion();
    const pluginDir = path.join(this.codexHome, "bundled_plugin");
    if (!fs.existsSync(pluginDir)) {
      fs.mkdirSync(pluginDir, { recursive: true });
    }

    // Write dummy/essential files for the plugin if not present
    const scriptsDir = path.join(pluginDir, "scripts");
    if (!fs.existsSync(scriptsDir)) {
      fs.mkdirSync(scriptsDir, { recursive: true });
    }

    return pythonExecutable;
  }
}
