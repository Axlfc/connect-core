import * as fs from "fs";
import * as path from "path";
import * as os from "os";

export interface CodexLoginHandle {
  api_key?: string;
  device_token?: string;
  expires_at?: number;
}

export class AuthenticationManager {
  private configPath: string;

  constructor() {
    this.configPath = path.join(os.homedir(), ".codex", "auth.json");
  }

  public getLoginHandle(): CodexLoginHandle {
    // 1. Check environment variables
    if (process.env.OPENAI_API_KEY) {
      return { api_key: process.env.OPENAI_API_KEY };
    }
    if (process.env.CODEX_API_KEY) {
      return { api_key: process.env.CODEX_API_KEY };
    }

    // 2. Check local persistence
    if (fs.existsSync(this.configPath)) {
      try {
        const raw = fs.readFileSync(this.configPath, "utf-8");
        return JSON.parse(raw) as CodexLoginHandle;
      } catch (e) {
        // ignore
      }
    }

    return {};
  }

  public saveLoginHandle(handle: CodexLoginHandle): void {
    const dir = path.dirname(this.configPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.configPath, JSON.stringify(handle, null, 2), "utf-8");
  }

  public clear(): void {
    if (fs.existsSync(this.configPath)) {
      fs.unlinkSync(this.configPath);
    }
  }
}
