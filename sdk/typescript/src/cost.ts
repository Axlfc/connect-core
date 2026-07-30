import * as fs from "fs";
import * as path from "path";
import { ScanCostLimitExceededError } from "./errors";

export interface ScanCost {
  promptTokens: number;
  completionTokens: number;
  totalCostUsd: number;
}

export class ScanCostTracker {
  private logPath: string;
  private maxCostUsd: number;

  constructor(sessionLogDir: string, maxCostUsd: number = 10.0) {
    this.logPath = path.join(sessionLogDir, "session_cost.json");
    this.maxCostUsd = maxCostUsd;
  }

  public getCost(): ScanCost {
    if (fs.existsSync(this.logPath)) {
      try {
        const raw = fs.readFileSync(this.logPath, "utf-8");
        return JSON.parse(raw) as ScanCost;
      } catch (e) {
        // ignore
      }
    }
    return { promptTokens: 0, completionTokens: 0, totalCostUsd: 0.0 };
  }

  public checkLimit() {
    const cost = this.getCost();
    if (cost.totalCostUsd > this.maxCostUsd) {
      throw new ScanCostLimitExceededError(
        `Operation aborted: total cost of $${cost.totalCostUsd.toFixed(4)} USD exceeds the configured maximum limit of $${this.maxCostUsd.toFixed(4)} USD.`
      );
    }
  }

  public writeDummyCost(cost: ScanCost) {
    const dir = path.dirname(this.logPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.logPath, JSON.stringify(cost, null, 2), "utf-8");
  }
}
